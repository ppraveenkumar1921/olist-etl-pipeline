import sys
import time

from src.analysis import run_analysis
from src.extract import extract_csv_tables, get_exchange_rates
from src.load import load_all
from src.quality import run_quality_checks
from src.transform import transform_all
from src.utils import get_logger

logger = get_logger("pipeline")


def timed(stage_name, func, *args, **kwargs):
    """Run one pipeline stage and log how long it took."""
    start = time.perf_counter()
    logger.info("START %s", stage_name)
    result = func(*args, **kwargs)
    logger.info("DONE  %s in %.1fs", stage_name, time.perf_counter() - start)
    return result


def run_pipeline():
    tables = timed("extract_csv", extract_csv_tables)
    rates = timed("extract_api", get_exchange_rates)
    clean = timed("transform", transform_all, tables, rates)
    timed("load", load_all, clean)
    timed("quality_checks", run_quality_checks)
    timed("analysis", run_analysis)


if __name__ == "__main__":
    start = time.perf_counter()
    try:
        run_pipeline()
    except Exception:
        logger.exception("PIPELINE FAILED")
        sys.exit(1)  # non-zero exit code lets schedulers detect the failure
    logger.info("PIPELINE SUCCEEDED in %.1fs", time.perf_counter() - start)