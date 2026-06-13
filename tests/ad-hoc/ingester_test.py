from src.logging_config import logger

logger.info("test_event", batch_num=0, status="success")
logger.error(
    "test_event",
    batch_num=1,
    status="error",
    error_type="PineconeApiException",
    error_msg="timeout",
)
