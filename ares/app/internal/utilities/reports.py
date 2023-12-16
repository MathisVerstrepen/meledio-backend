import os
import json
import aiofiles # type: ignore

from app.utils.loggers import base_logger as logger


async def get_all_reports() -> list:
    """Get all reports id and creation date sorted by creation date.

    Returns:
        list: The list of reports.
    """

    logger.info("[Reports] Getting all reports")
    reports = []
    for file in os.listdir("/bacchus/reports/wizard/"):
        if file.endswith(".json"):
            file_path = os.path.join("/bacchus/reports/wizard/", file)
            async with aiofiles.open(file_path, mode="r") as f:
                data = json.loads(await f.read())
                reports.append(
                    {
                        "report_id": data.get("report_id"),
                        "creation_date": data.get("creation_date"),
                    }
                )

    reports = sorted(reports, key=lambda k: k["creation_date"], reverse=True)

    return reports


async def get_one_report(report_id: str) -> dict:
    """For a given report id, returns the report data.

    Args:
        report_id (str): The report id.

    Returns:
        dict: The report data.
    """

    logger.info("[Reports] Getting report [%s]", report_id)

    try:
        async with aiofiles.open(
            f"/bacchus/reports/wizard/{report_id}.json", mode="r"
        ) as f:
            data = json.loads(await f.read())
            return data
    except FileNotFoundError:
        logger.error("[Reports] Report [%s] not found", report_id)
        return None
