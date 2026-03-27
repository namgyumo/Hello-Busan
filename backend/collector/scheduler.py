"""
데이터 수집 스케줄러
- APScheduler 기반 주기적 수집
- 수집기별 독립 스케줄 관리
- 수집 후 comfort_scores 자동 재계산
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.collector.tourism import TourismCollector
from backend.collector.crowd import CrowdCollector
from backend.collector.weather import WeatherCollector
from backend.collector.transport import TransportCollector
from backend.collector.busan_api import BusanApiCollector
from backend.collector.festivals import FestivalCollector
from backend.services.score_calculator import ScoreCalculator
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
            "busan_api": BusanApiCollector(),
            "festivals": FestivalCollector(),
        }
        self.score_calculator = ScoreCalculator()
        self._setup_jobs()

    def _setup_jobs(self):
        """스케줄 등록"""
        # 관광지 정보: 매일 1회
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=24),
            args=["tourism"],
            id="tourism_collector",
            name="관광지 정보 수집",
        )

        # 부산시 공공데이터 API: 매일 1회
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=24),
            args=["busan_api"],
            id="busan_api_collector",
            name="부산시 공공데이터 API 수집",
        )

        # 혼잡도: 10분마다 → 수집 후 comfort_scores 재계산
        self.scheduler.add_job(
            self._run_crowd_and_recalc,
            trigger=IntervalTrigger(minutes=10),
            id="crowd_collector",
            name="혼잡도 수집 + 쾌적도 재계산",
        )

        # 날씨: 1시간마다 → 수집 후 comfort_scores 재계산
        self.scheduler.add_job(
            self._run_weather_and_recalc,
            trigger=IntervalTrigger(hours=1),
            id="weather_collector",
            name="날씨 수집 + 쾌적도 재계산",
        )

        # 교통: 6시간마다
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=6),
            args=["transport"],
            id="transport_collector",
            name="교통 정보 수집",
        )

        # 축제/이벤트: 매일 1회
        self.scheduler.add_job(
            self._run_collector,
            trigger=IntervalTrigger(hours=24),
            args=["festivals"],
            id="festivals_collector",
            name="축제/이벤트 수집",
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

    async def _run_crowd_and_recalc(self):
        """혼잡도 수집 → comfort_scores 재계산 → SSE 브로드캐스트"""
        logger.info("수집 시작: crowd + comfort 재계산")

        # 혼잡도 수집
        result = await self.collectors["crowd"].run()
        logger.info(f"혼잡도 수집: {result}")

        # comfort_scores 재계산
        updated = await self.score_calculator.calculate_all()
        logger.info(f"comfort_scores {updated}건 갱신")

        # SSE 브로드캐스트
        await self._broadcast_comfort_update()

    async def _run_weather_and_recalc(self):
        """날씨 수집 → comfort_scores 재계산"""
        logger.info("수집 시작: weather + comfort 재계산")

        result = await self.collectors["weather"].run()
        logger.info(f"날씨 수집: {result}")

        updated = await self.score_calculator.calculate_all()
        logger.info(f"comfort_scores {updated}건 갱신")

        await self._broadcast_comfort_update()

    async def _broadcast_comfort_update(self):
        """SSE 클라이언트에 업데이트 알림"""
        try:
            from backend.api.events import broadcast_update
            from backend.db.supabase import get_supabase

            sb = get_supabase()
            spots = (
                sb.table("tourist_spots")
                .select("id, name, lat, lng")
                .eq("is_active", True)
                .execute()
            )

            comfort_scores = (
                sb.table("comfort_scores")
                .select("spot_id, total_score, crowd_score, grade")
                .execute()
            )

            # comfort 데이터 매핑
            comfort_map = {
                str(c["spot_id"]): c for c in (comfort_scores.data or [])
            }

            spot_list = []
            heatmap_points = []
            for s in (spots.data or []):
                sid = str(s["id"])
                c = comfort_map.get(sid, {})
                spot_list.append({
                    "id": sid,
                    "name": s["name"],
                    "lat": s["lat"],
                    "lng": s["lng"],
                    "comfort_score": c.get("total_score", 50),
                    "comfort_grade": c.get("grade", "보통"),
                })
                crowd_score = c.get("crowd_score", 50)
                if crowd_score is None:
                    crowd_score = 50
                intensity = round(1 - (crowd_score / 100), 2)
                heatmap_points.append([s["lat"], s["lng"], intensity])

            await broadcast_update("comfort_update", {"spots": spot_list})
            await broadcast_update("heatmap_update", {"points": heatmap_points})

        except Exception as e:
            logger.error(f"SSE 브로드캐스트 실패: {e}")

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

        # nightview 카테고리 시딩 (tourism 수집 후에도 재확인)
        try:
            nightview_count = await self.collectors["tourism"].seed_nightview()
            results["nightview_seed"] = {"updated": nightview_count}
        except Exception as e:
            logger.error(f"nightview 시딩 실패: {e}")

        # 전체 수집 후 comfort_scores 계산
        updated = await self.score_calculator.calculate_all()
        results["comfort_recalc"] = {"updated": updated}

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
