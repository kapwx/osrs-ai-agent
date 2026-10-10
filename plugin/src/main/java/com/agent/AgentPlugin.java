package com.agent;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.inject.Provides;
import java.awt.Canvas;
import java.awt.Rectangle;
import java.awt.event.KeyEvent;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.api.GameState;
import net.runelite.api.Item;
import net.runelite.api.ItemContainer;
import net.runelite.api.InventoryID;
import net.runelite.api.ItemComposition;
import net.runelite.api.MenuAction;
import net.runelite.api.NPC;
import net.runelite.api.Perspective;
import net.runelite.api.Player;
import net.runelite.api.Point;
import net.runelite.api.Skill;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameTick;
import net.runelite.api.widgets.ComponentID;
import net.runelite.api.widgets.Widget;
import net.runelite.client.callback.ClientThread;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.game.ItemManager;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

@Slf4j
@PluginDescriptor(
    name = "OSRS AI Agent Bridge",
    description = "Streams telemetry to AI Brain and executes autonomous actions natively inside RuneLite",
    tags = {"ai", "bot", "agent", "bridge", "telemetry", "executor"}
)
public class AgentPlugin extends Plugin
{
    private static final MediaType JSON_MEDIA_TYPE = MediaType.parse("application/json; charset=utf-8");

    @Inject
    private Client client;

    @Inject
    private ClientThread clientThread;

    @Inject
    private AgentConfig config;

    @Inject
    private ItemManager itemManager;

    @Inject
    private OkHttpClient okHttpClient;

    @Inject
    private Gson gson;

    private int tickCount = 0;
    private String lastExecutedAction = "";
    private String lastExecutedTarget = "";
    private int lastExecutedTick = 0;

    @Provides
    AgentConfig provideConfig(ConfigManager configManager)
    {
        return configManager.getConfig(AgentConfig.class);
    }

    @Override
    protected void startUp()
    {
        log.info("OSRS AI Agent Bridge plugin started with native action executor!");
    }

    @Override
    protected void shutDown()
    {
        log.info("OSRS AI Agent Bridge plugin stopped.");
    }

    @Subscribe
    public void onGameTick(GameTick event)
    {
        if (!config.enabled() || client.getGameState() != GameState.LOGGED_IN)
        {
            return;
        }

        tickCount++;
        if (tickCount % Math.max(1, config.tickInterval()) != 0)
        {
            return;
        }

        Player localPlayer = client.getLocalPlayer();
        if (localPlayer == null)
        {
            return;
        }

        Map<String, Object> state = new HashMap<>();

        // 1. Player basic state
        WorldPoint playerLocation = localPlayer.getWorldLocation();
        Map<String, Object> locationMap = new HashMap<>();
        locationMap.put("x", playerLocation.getX());
        locationMap.put("y", playerLocation.getY());
        locationMap.put("plane", playerLocation.getPlane());
        state.put("location", locationMap);

        state.put("animation", localPlayer.getAnimation());
        state.put("interacting", localPlayer.getInteracting() != null ? localPlayer.getInteracting().getName() : null);

        // Dialogue check (very common on Tutorial Island & Quests)
        Widget npcDialog = client.getWidget(ComponentID.DIALOG_NPC_TEXT);
        Widget playerDialog = client.getWidget(ComponentID.DIALOG_PLAYER_TEXT);
        Widget optionDialog = client.getWidget(ComponentID.DIALOG_OPTION_OPTIONS);
        Widget spriteDialog = client.getWidget(ComponentID.DIALOG_SPRITE_TEXT);
        boolean isDialogueActive = (npcDialog != null && !npcDialog.isHidden()) ||
                                   (playerDialog != null && !playerDialog.isHidden()) ||
                                   (optionDialog != null && !optionDialog.isHidden()) ||
                                   (spriteDialog != null && !spriteDialog.isHidden());
        state.put("dialogue_active", isDialogueActive);

        // Stats
        Map<String, Object> stats = new HashMap<>();
        stats.put("hp_current", client.getBoostedSkillLevel(Skill.HITPOINTS));
        stats.put("hp_max", client.getRealSkillLevel(Skill.HITPOINTS));
        stats.put("prayer_current", client.getBoostedSkillLevel(Skill.PRAYER));
        stats.put("prayer_max", client.getRealSkillLevel(Skill.PRAYER));
        stats.put("run_energy", client.getEnergy());
        state.put("stats", stats);

        // 2. Inventory & slot screen coordinates
        ItemContainer inventory = client.getItemContainer(InventoryID.INVENTORY);
        Widget invWidget = client.getWidget(ComponentID.INVENTORY_CONTAINER);
        List<Map<String, Object>> items = new ArrayList<>();
        if (inventory != null)
        {
            Item[] rawItems = inventory.getItems();
            for (int slot = 0; slot < rawItems.length; slot++)
            {
                Item item = rawItems[slot];
                if (item != null && item.getId() > 0)
                {
                    ItemComposition comp = itemManager.getItemComposition(item.getId());
                    Map<String, Object> itemData = new HashMap<>();
                    itemData.put("slot", slot);
                    itemData.put("id", item.getId());
                    itemData.put("name", comp != null ? comp.getName() : "Unknown");
                    itemData.put("quantity", item.getQuantity());

                    if (invWidget != null)
                    {
                        Widget slotWidget = invWidget.getChild(slot);
                        if (slotWidget != null)
                        {
                            Rectangle bounds = slotWidget.getBounds();
                            if (bounds != null && bounds.width > 0)
                            {
                                itemData.put("canvas_x", (int) bounds.getCenterX());
                                itemData.put("canvas_y", (int) bounds.getCenterY());
                            }
                        }
                    }

                    items.add(itemData);
                }
            }
        }
        state.put("inventory", items);
        state.put("inventory_count", items.size());

        // 3. Nearby NPCs with 2D Canvas & Minimap Screen Projections
        List<Map<String, Object>> npcs = new ArrayList<>();
        for (NPC npc : client.getNpcs())
        {
            if (npc != null && npc.getName() != null)
            {
                WorldPoint npcLoc = npc.getWorldLocation();
                int distance = playerLocation.distanceTo(npcLoc);
                if (distance <= 15)
                {
                    Map<String, Object> npcData = new HashMap<>();
                    npcData.put("id", npc.getId());
                    npcData.put("index", npc.getIndex());
                    npcData.put("name", npc.getName());
                    npcData.put("distance", distance);
                    npcData.put("x", npcLoc.getX());
                    npcData.put("y", npcLoc.getY());

                    LocalPoint localPoint = npc.getLocalLocation();
                    if (localPoint != null)
                    {
                        Point canvasPt = Perspective.localToCanvas(client, localPoint, client.getPlane());
                        if (canvasPt != null)
                        {
                            npcData.put("canvas_x", canvasPt.getX());
                            npcData.put("canvas_y", canvasPt.getY());
                        }

                        Point minimapPt = Perspective.localToMinimap(client, localPoint);
                        if (minimapPt != null)
                        {
                            npcData.put("minimap_x", minimapPt.getX());
                            npcData.put("minimap_y", minimapPt.getY());
                        }
                    }

                    npcs.add(npcData);
                }
            }
        }
        state.put("nearby_npcs", npcs);

        // Send state to backend asynchronously and execute returned AI action natively
        sendStateAsync(state);
    }

    private void sendStateAsync(Map<String, Object> state)
    {
        String json = gson.toJson(state);
        RequestBody body = RequestBody.create(JSON_MEDIA_TYPE, json);
        Request request = new Request.Builder()
            .url(config.serverUrl())
            .post(body)
            .build();

        okHttpClient.newCall(request).enqueue(new Callback()
        {
            @Override
            public void onFailure(Call call, IOException e)
            {
                // Silently ignore connection drops
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException
            {
                try
                {
                    if (response.isSuccessful() && response.body() != null)
                    {
                        String respBody = response.body().string();
                        JsonObject obj = gson.fromJson(respBody, JsonObject.class);
                        if (obj != null && obj.has("action") && !obj.get("action").isJsonNull())
                        {
                            JsonObject actionObj = obj.getAsJsonObject("action");
                            clientThread.invoke(() -> handleAction(actionObj));
                        }
                    }
                    response.close();
                }
                catch (Exception ignored)
                {
                }
            }
        });
    }

    /**
     * Executes AI actions directly inside the RuneLite client thread.
     * Works 100% in Alt+Tab, minimized, or background without moving user's OS mouse!
     */
    private void handleAction(JsonObject act)
    {
        if (act == null || client.getGameState() != GameState.LOGGED_IN)
        {
            return;
        }

        String actionType = act.has("action_type") && !act.get("action_type").isJsonNull()
            ? act.get("action_type").getAsString() : "IDLE";

        if ("IDLE".equals(actionType))
        {
            return;
        }

        // 1. Dialogue progression reflex
        if ("CONTINUE_DIALOGUE".equals(actionType))
        {
            Canvas canvas = client.getCanvas();
            if (canvas != null)
            {
                KeyEvent press = new KeyEvent(canvas, KeyEvent.KEY_PRESSED, System.currentTimeMillis(), 0, KeyEvent.VK_SPACE, ' ');
                KeyEvent release = new KeyEvent(canvas, KeyEvent.KEY_RELEASED, System.currentTimeMillis(), 0, KeyEvent.VK_SPACE, ' ');
                canvas.dispatchEvent(press);
                canvas.dispatchEvent(release);
                log.info("[NATIVE AI] Advanced dialogue via Spacebar");
            }
            return;
        }

        String targetName = act.has("target_name") && !act.get("target_name").isJsonNull()
            ? act.get("target_name").getAsString() : "";
        String lowerTarget = targetName.toLowerCase().trim();

        Player localPlayer = client.getLocalPlayer();

        // Prevent spamming the exact same action while character is already walking or interacting
        if (actionType.equals(lastExecutedAction) && targetName.equals(lastExecutedTarget))
        {
            if (localPlayer != null && localPlayer.getInteracting() != null)
            {
                return; // already talking or fighting target
            }
            if (tickCount - lastExecutedTick < 4)
            {
                return; // still walking towards target
            }
        }

        // 2. NPC Interactions (Talk-to, Walk-to, Attack)
        if ("TALK_TO_NPC".equals(actionType) || "WALK_TO".equals(actionType) || "ATTACK_NPC".equals(actionType))
        {
            NPC targetNpc = null;
            if (!lowerTarget.isEmpty())
            {
                for (NPC npc : client.getNpcs())
                {
                    if (npc != null && npc.getName() != null)
                    {
                        String npcName = npc.getName().toLowerCase();
                        if (npcName.contains(lowerTarget) || lowerTarget.contains(npcName))
                        {
                            targetNpc = npc;
                            break;
                        }
                    }
                }
            }

            if (targetNpc != null)
            {
                MenuAction menuAction = "ATTACK_NPC".equals(actionType)
                    ? MenuAction.NPC_SECOND_OPTION
                    : MenuAction.NPC_FIRST_OPTION;
                String option = "ATTACK_NPC".equals(actionType) ? "Attack" : "Talk-to";

                log.info("[NATIVE AI] Interacting with NPC: {} ({})", targetNpc.getName(), menuAction);
                client.menuAction(0, 0, menuAction, targetNpc.getIndex(), 0, option, targetNpc.getName());

                lastExecutedAction = actionType;
                lastExecutedTarget = targetName;
                lastExecutedTick = tickCount;
                return;
            }
            else if (act.has("coordinates") && !act.get("coordinates").isJsonNull())
            {
                JsonObject coords = act.getAsJsonObject("coordinates");
                int targetX = coords.get("x").getAsInt();
                int targetY = coords.get("y").getAsInt();
                WorldPoint wp = new WorldPoint(targetX, targetY, client.getPlane());
                LocalPoint lp = LocalPoint.fromWorld(client, wp);
                if (lp != null)
                {
                    log.info("[NATIVE AI] Walking to scene coordinates: ({}, {})", lp.getSceneX(), lp.getSceneY());
                    client.menuAction(lp.getSceneX(), lp.getSceneY(), MenuAction.WALK, 0, 0, "Walk here", "");

                    lastExecutedAction = actionType;
                    lastExecutedTarget = targetName;
                    lastExecutedTick = tickCount;
                    return;
                }
            }
        }

        // 3. Eating Food from Inventory
        if ("EAT_FOOD".equals(actionType))
        {
            ItemContainer inv = client.getItemContainer(InventoryID.INVENTORY);
            if (inv != null)
            {
                Item[] items = inv.getItems();
                for (int slot = 0; slot < items.length; slot++)
                {
                    Item item = items[slot];
                    if (item != null && item.getId() > 0)
                    {
                        ItemComposition comp = itemManager.getItemComposition(item.getId());
                        if (comp != null && (lowerTarget.isEmpty() || comp.getName().toLowerCase().contains(lowerTarget)))
                        {
                            log.info("[NATIVE AI] Consuming food: {} (slot {})", comp.getName(), slot);
                            client.menuAction(slot, ComponentID.INVENTORY_CONTAINER, MenuAction.ITEM_FIRST_OPTION, item.getId(), item.getId(), "Eat", comp.getName());

                            lastExecutedAction = actionType;
                            lastExecutedTarget = targetName;
                            lastExecutedTick = tickCount;
                            return;
                        }
                    }
                }
            }
        }
    }
}
