"""
데이터 수집 스케줄러
- APScheduler 기반 주기적 수집
- 수집기별 독립 스케줄 관리
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.collector.tourism import TourismCollector
from backend.collector.crowd import CrowdCollector
from backend.collector.weather import WeatherCollector
from backend.collector.transport import TransportCollector
import logging

logger = logging.getLogger(__name__)


class CollectorScheduler:
    """수집기 스케줄러"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.collectors = {
            "tourism": TourismCollector(),
            "crowd": CrowdCollector(),
            "weather": WeatherCollector(),
            "transport": TransportCollector(),
        }
        self._setup_jobs()

    def _setup_jobs(self):
        """스케줄 등록"""
        # 관광지 정보: 매일 1회 (새벽 3시)
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=24),
            args=["tourism"],
            id="tourism_collector",
            name="관광지 정보 수집",
        )

        # 혼잡도: 10분마다
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(minutes=10),
            args=["crowd"],
            id="crowd_collector",
            name="혼잡도 수집",
        )

        # 날씨: 1시간마다
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=1),
            args=["weather"],
            id="weather_collector",
            name="날씨 수집",
        )

        # 교통: 6시간마다
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=6),
            args=["transport"],
            id="transport_collector",
            name="교통 정보 수집",
        )

    async def _run_collector(self, name: str):
        """수집기 실행"""
        collector = self.collectors.get(name)
        if not collector:
            logger.error(f"알 수 없는 수집기: {name}")
            return

        logger.info(f"수집 시작: {name}")
        result = await collector.run()
        logger.info(f"수집 완료: {name} -> {result}")

    def start(self):
        """스케줄러 시작"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("수집 스케줄러 시작")

    def stop(self):
        """스케줄러 중지"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("수집 스케줄러 중지")

    async def run_all_now(self):
        """모든 수집기 즉시 실행 (초기화용)"""
        results = {}
        for name, collector in self.collectors.items():
            logger.info(f"즉시 수집: {name}")
            results[name] = await collector.run()
        return results

    def get_status(self) -> dict:
        """스케줄러 상태"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })
        return {
            "running": self.scheduler.running,
            "jobs": jobs,
        }
