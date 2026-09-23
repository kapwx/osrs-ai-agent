package com.agent;

import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;

@ConfigGroup("osrsaiagent")
public interface AgentConfig extends Config
{
    @ConfigItem(
        keyName = "serverUrl",
        name = "Backend Server URL",
        description = "URL of the local Python brain middleware",
        position = 1
    )
    default String serverUrl()
    {
        return "http://localhost:8000/api/state";
    }

    @ConfigItem(
        keyName = "tickInterval",
        name = "Tick Interval",
        description = "Send state every N game ticks (1 tick = 600ms)",
        position = 2
    )
    default int tickInterval()
    {
        return 2;
    }

    @ConfigItem(
        keyName = "enabled",
        name = "Enable Telemetry",
        description = "Toggle telemetry streaming to the backend",
        position = 3
    )
    default boolean enabled()
    {
        return true;
    }
}
