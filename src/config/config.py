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

    def get_database_config(self, value):
        return self.connection.get(value, {})

    def get_application_config(self, value):
        return self.application.get(value, {})
