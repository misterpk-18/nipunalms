"""Application logging. Log timestamps are IST, whatever the server's clock zone is."""
import logging
from datetime import datetime

from config.timezone import IST


class _IstFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        moment = datetime.fromtimestamp(record.created, IST)
        return moment.strftime(datefmt) if datefmt else moment.strftime("%Y-%m-%d %H:%M:%S") + f",{int(record.msecs):03d}"


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), force=True)
    formatter = _IstFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)
    # AWS libraries log every request and header at DEBUG; keep them to warnings
    for name in ("boto3", "botocore", "s3transfer", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
