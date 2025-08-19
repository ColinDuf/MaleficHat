import logging

class DiscordLogHandler(logging.Handler):
    def __init__(self, bot, channel_id):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    def emit(self, record):
        log_entry = self.format(record)
        async def send_log():
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                try:
                    await channel.send(log_entry)
                except Exception as e:
                    print("Error sending log to Discord:", e)
        self.bot.loop.create_task(send_log())
