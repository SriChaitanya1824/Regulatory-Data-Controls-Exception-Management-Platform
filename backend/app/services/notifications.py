import structlog

log = structlog.get_logger()


class NotificationService:
    def send(self, event: str, recipient: str, context: dict) -> None:
        log.info("notification", event=event, recipient=recipient, context=context, mode="local-log")


notifications = NotificationService()

