"""Read-only process resource measurements."""

from dataclasses import asdict, dataclass
import resource
import sys
from time import monotonic


_STARTED_AT = monotonic()


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    uptime_seconds: float
    process_cpu_user_seconds: float
    process_cpu_system_seconds: float
    maximum_resident_set_bytes: int

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def resource_snapshot() -> ResourceSnapshot:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    resident_bytes = int(usage.ru_maxrss)
    if sys.platform != "darwin":
        resident_bytes *= 1_024
    return ResourceSnapshot(
        uptime_seconds=max(monotonic() - _STARTED_AT, 0.0),
        process_cpu_user_seconds=max(usage.ru_utime, 0.0),
        process_cpu_system_seconds=max(usage.ru_stime, 0.0),
        maximum_resident_set_bytes=max(resident_bytes, 0),
    )
