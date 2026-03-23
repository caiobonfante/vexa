"""Container profile definitions — what each profile needs."""

from app import config


def get_profile(profile: str) -> dict:
    """Get image, resources, and default config for a profile."""
    profiles = {
        "agent": {
            "image": config.AGENT_IMAGE,
            "resources": {"memory": "512m"},
            "idle_timeout": config.AGENT_IDLE_TIMEOUT,
            "auto_remove": False,
            "ports": {},
        },
        "browser": {
            "image": config.BROWSER_IMAGE,
            "resources": {"memory": "2g", "shm_size": 2 * 1024 * 1024 * 1024},
            "idle_timeout": config.BROWSER_IDLE_TIMEOUT,
            "auto_remove": False,
            "ports": {
                "6080/tcp": {},   # VNC web
                "9223/tcp": {},   # CDP proxy
                "22/tcp": {},     # SSH
            },
        },
        "meeting": {
            "image": config.MEETING_IMAGE,
            "resources": {"memory": "2g", "shm_size": 2 * 1024 * 1024 * 1024},
            "idle_timeout": 0,  # Meeting bots don't idle-timeout; they exit on meeting end
            "auto_remove": True,
            "ports": {},
        },
    }
    return profiles.get(profile, profiles["agent"])
