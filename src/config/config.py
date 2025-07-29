import yaml
import os

class Config:
    def __init__(self, path="src/config.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)

        self.connection = data.get("connection", {})
        self.bots = data.get("bots", {})
        self.application = data.get("application", {})

    def get_bot_config(self, bot_name):
        return self.bots.get(bot_name, {})

    def get_database_config(self, key, default=None):
        value = self.connection.get(key, default)
        if value is None:
            return default
        return value

    def get_application_config(self, key, default=None):
        value = self.application.get(key, default)
        if value is None:
            return default
        return value
