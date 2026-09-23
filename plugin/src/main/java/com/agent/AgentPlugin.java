package com.agent;

import com.google.gson.Gson;
import com.google.inject.Provides;
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
import net.runelite.api.NPC;
import net.runelite.api.Player;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameTick;
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
    description = "Streams local player and environment state to AI Brain Middleware",
    tags = {"ai", "bot", "agent", "bridge", "telemetry"}
)
public class AgentPlugin extends Plugin
{
    private static final MediaType JSON_MEDIA_TYPE = MediaType.parse("application/json; charset=utf-8");

    @Inject
    private Client client;

    @Inject
    private AgentConfig config;

    @Inject
    private ItemManager itemManager;

    @Inject
    private OkHttpClient okHttpClient;

    @Inject
    private Gson gson;

    private int tickCount = 0;

    @Provides
    AgentConfig provideConfig(ConfigManager configManager)
    {
        return configManager.getConfig(AgentConfig.class);
    }

    @Override
    protected void startUp()
    {
        log.info("OSRS AI Agent Bridge plugin started!");
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

        // Stats
        Map<String, Object> stats = new HashMap<>();
        stats.put("hp_current", client.getBoostedSkillLevel(Skill.HITPOINTS));
        stats.put("hp_max", client.getRealSkillLevel(Skill.HITPOINTS));
        stats.put("prayer_current", client.getBoostedSkillLevel(Skill.PRAYER));
        stats.put("prayer_max", client.getRealSkillLevel(Skill.PRAYER));
        stats.put("run_energy", client.getEnergy());
        state.put("stats", stats);

        // 2. Inventory
        ItemContainer inventory = client.getItemContainer(InventoryID.INVENTORY);
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
                    items.add(itemData);
                }
            }
        }
        state.put("inventory", items);
        state.put("inventory_count", items.size());

        // 3. Nearby NPCs
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
                    npcs.add(npcData);
                }
            }
        }
        state.put("nearby_npcs", npcs);

        // Send state to backend asynchronously
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
                // Silently ignore connection drops to avoid spamming client logs
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException
            {
                try
                {
                    response.close();
                }
                catch (Exception ignored)
                {
                }
            }
        });
    }
}
