#!/usr/bin/env python3
"""
完整的 FIT 檔案處理與統計分析系統示例
使用抽象層設計，分離業務邏輯與儲存實作
"""
import logging
from datetime import datetime
from pathlib import Path

from peakflow import (
    ElasticsearchStorage, 
    FitFileProcessor, 
    AdvancedStatistics,
    DataType,
    QueryFilter,
    StorageError
)
from peakflow.utils import get_logger


# 設定日誌
logger = get_logger("fitness_analytics_demo")


class FitnessAnalyticsPlatform:
    """健身數據分析平台"""
    
    def __init__(self, es_config: dict = None):
        """初始化平台"""
        self.es_config = es_config or {
            'hosts': ['http://localhost:9200'],
            'username': 'elastic',
            'password': 'password',
            'verify_certs': False,
            'timeout': 30,
            'max_retries': 3
        }
        
        # 初始化儲存層
        self.storage = ElasticsearchStorage()
        
        # 初始化處理器
        self.processor = None
        self.statistics = None
        
        self._initialize()
    
    def _initialize(self):
        """初始化系統"""
        try:
            # 初始化儲存連接
            logger.info("🔧 Initializing storage connection...")
            if not self.storage.initialize(self.es_config):
                raise StorageError("Failed to initialize storage")
            
            # 建立索引
            logger.info("🏗️ Creating indices...")
            self.storage.create_indices(force_recreate=False)
            
            # 初始化處理器和統計模組
            self.processor = FitFileProcessor(self.storage)
            self.statistics = AdvancedStatistics(self.storage)
            
            logger.info("✅ Platform initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Platform initialization failed: {e}")
            raise
    
    def process_fit_file(self, file_path: str, activity_id: str, user_id: str) -> dict:
        """處理 FIT 檔案"""
        logger.info(f"📁 Processing FIT file: {file_path}")
        
        try:
            result = self.processor.process(file_path, user_id, activity_id)
            
            logger.info(f"✅ FIT file processed successfully:")
            logger.info(f"   📊 Sessions: {result.metadata.get('sessions', 0)}")
            logger.info(f"   🏃 Records: {result.metadata.get('records', 0)}")
            logger.info(f"   🏁 Laps: {result.metadata.get('laps', 0)}")
            logger.info(f"   ✅ Total Success: {result.successful_records}")
            logger.info(f"   ❌ Total Failed: {result.failed_records}")
            
            return {
                "success": result.status.value in ["completed", "partially_completed"],
                "stats": {
                    "session": result.metadata.get('sessions', 0),
                    "record": result.metadata.get('records', 0),
                    "lap": result.metadata.get('laps', 0)
                },
                "total_indexed": result.successful_records,
                "errors": result.errors if result.errors else None,
                "status": result.status.value,
                "processing_time": result.processing_time
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to process FIT file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_activity_dashboard(self, activity_id: str) -> dict:
        """取得活動儀表板"""
        logger.info(f"📊 Generating activity dashboard for: {activity_id}")
        
        try:
            # 活動摘要
            summary = self.processor.get_activity_summary(activity_id)
            if not summary:
                return {"error": "Activity not found"}
            
            # 心率分析
            try:
                hr_analysis = self.statistics.get_heart_rate_analysis(
                    summary['user_id'], activity_id
                )
            except Exception as e:
                logger.warning(f"Heart rate analysis failed: {e}")
                hr_analysis = {"error": "Heart rate analysis not available"}
            
            # 分段分析
            try:
                lap_analysis = self.statistics.get_lap_performance_analysis(activity_id)
            except Exception as e:
                logger.warning(f"Lap analysis failed: {e}")
                lap_analysis = {"error": "Lap analysis not available"}
            
            # GPS 軌跡
            try:
                gps_track = self.processor.get_gps_trajectory(activity_id)
            except Exception as e:
                logger.warning(f"GPS trajectory failed: {e}")
                gps_track = []
            
            dashboard = {
                "activity_summary": summary,
                "heart_rate_analysis": hr_analysis,
                "lap_analysis": lap_analysis,
                "gps_track_points": len(gps_track),
                "gps_track": gps_track[:100] if gps_track else [],  # 限制返回數量
                "generated_at": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Dashboard generated successfully")
            return dashboard
            
        except Exception as e:
            logger.error(f"❌ Failed to generate dashboard: {e}")
            return {"error": str(e)}
    
    def get_user_analytics(self, user_id: str, days: int = 30) -> dict:
        """取得用戶分析報告"""
        logger.info(f"📈 Generating user analytics for: {user_id}")
        
        try:
            # 運動表現分析
            try:
                performance = self.processor.get_performance_analytics(user_id, days)
            except Exception as e:
                logger.warning(f"Performance analytics failed: {e}")
                performance = {"error": "Performance analytics not available"}
            
            # 活動分布
            try:
                distribution = self.statistics.get_activity_distribution(user_id, days)
            except Exception as e:
                logger.warning(f"Activity distribution failed: {e}")
                distribution = {"error": "Activity distribution not available"}
            
            # 表現趨勢
            try:
                trends = self.statistics.get_performance_trends(user_id, months=6)
            except Exception as e:
                logger.warning(f"Performance trends failed: {e}")
                trends = {"error": "Performance trends not available"}
            
            # 訓練負荷分析
            try:
                training_load = self.statistics.get_training_load_analysis(user_id, weeks=4)
            except Exception as e:
                logger.warning(f"Training load analysis failed: {e}")
                training_load = {"error": "Training load analysis not available"}
            
            # 地理分析
            try:
                geographic = self.statistics.get_geographic_analysis(user_id, days)
            except Exception as e:
                logger.warning(f"Geographic analysis failed: {e}")
                geographic = {"error": "Geographic analysis not available"}
            
            analytics = {
                "user_id": user_id,
                "analysis_period_days": days,
                "performance_analytics": performance,
                "activity_distribution": distribution,
                "performance_trends": trends,
                "training_load": training_load,
                "geographic_analysis": geographic,
                "generated_at": datetime.now().isoformat()
            }
            
            logger.info(f"✅ User analytics generated successfully")
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Failed to generate user analytics: {e}")
            return {"error": str(e)}
    
    def search_activities(self, user_id: str, filters: dict = None) -> dict:
        """搜尋活動"""
        logger.info(f"🔍 Searching activities for user: {user_id}")
        
        try:
            activities = self.processor.search_activities(user_id, filters)
            
            return {
                "total_found": len(activities),
                "activities": activities,
                "filters_applied": filters or {},
                "search_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Activity search failed: {e}")
            return {"error": str(e)}
    
    def compare_activities(self, activity_ids: list) -> dict:
        """比較多個活動"""
        logger.info(f"⚖️ Comparing activities: {activity_ids}")
        
        try:
            comparison = self.statistics.compare_activities_legacy(activity_ids)
            return comparison
            
        except Exception as e:
            logger.error(f"❌ Activity comparison failed: {e}")
            return {"error": str(e)}
    
    def get_system_stats(self) -> dict:
        """取得系統統計"""
        logger.info("📊 Getting system statistics")
        
        try:
            stats = {}
            for data_type in [DataType.SESSION, DataType.RECORD, DataType.LAP]:
                stats[data_type.value] = self.storage.get_stats(data_type)
            
            return {
                "system_stats": stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get system stats: {e}")
            return {"error": str(e)}
    
    def delete_activity(self, activity_id: str) -> dict:
        """刪除活動"""
        logger.info(f"🗑️ Deleting activity: {activity_id}")
        
        try:
            deleted_counts = {}
            
            for data_type in [DataType.SESSION, DataType.RECORD, DataType.LAP]:
                query_filter = QueryFilter().add_term_filter("activity_id", activity_id)
                count = self.storage.delete_by_query(data_type, query_filter)
                deleted_counts[data_type.value] = count
            
            total_deleted = sum(deleted_counts.values())
            
            logger.info(f"✅ Activity deleted: {deleted_counts}")
            
            return {
                "success": True,
                "deleted_counts": deleted_counts,
                "total_deleted": total_deleted
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete activity: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def main():
    """主函數示例"""
    
    # 初始化平台
    try:
        platform = FitnessAnalyticsPlatform()
    except Exception as e:
        logger.error(f"Failed to initialize platform: {e}")
        return
    
    # 示例：處理 FIT 檔案
    fit_file_path = '/home/aiuser/codetrekking/storage/garmin/example@gmail.com/activities/19329066809_ACTIVITY.fit'
    activity_id = '19329066809'
    user_id = 'example@gmail.com'
    
    if Path(fit_file_path).exists():
        # 處理 FIT 檔案
        logger.info("=" * 80)
        logger.info("🔄 Processing FIT File")
        logger.info("=" * 80)
        
        result = platform.process_fit_file(fit_file_path, activity_id, user_id)
        if result["success"]:
            logger.success(f"✅ Processing completed successfully")
            logger.info(f"📊 Indexed: {result['total_indexed']} documents")
            logger.info(f"⏱️ Processing time: {result.get('processing_time', 0):.2f}s")
            logger.info(f"📈 Status: {result.get('status', 'unknown')}")
        else:
            logger.error(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
            return
        
        # 生成活動儀表板
        logger.info("\n" + "=" * 80)
        logger.info("📊 Activity Dashboard")
        logger.info("=" * 80)
        
        dashboard = platform.get_activity_dashboard(activity_id)
        if "error" not in dashboard:
            summary = dashboard["activity_summary"]
            logger.info(f"🏃 Sport: {summary.get('sport', 'N/A')}")
            logger.info(f"📏 Distance: {summary.get('total_distance', 0):.2f} m")
            logger.info(f"⏱️ Time: {summary.get('total_timer_time', 0):.0f} s")
            logger.info(f"💓 Avg HR: {summary.get('avg_heart_rate', 0)} bpm")
            logger.info(f"🏁 Laps: {dashboard['lap_analysis'].get('total_laps', 0)}")
            logger.info(f"📍 GPS Points: {dashboard['gps_track_points']}")
        else:
            logger.error(f"❌ Dashboard generation failed: {dashboard['error']}")
        
        # 用戶分析
        logger.info("\n" + "=" * 80)
        logger.info("📈 User Analytics (30 days)")
        logger.info("=" * 80)
        
        analytics = platform.get_user_analytics(user_id, 30)
        if "error" not in analytics:
            perf = analytics["performance_analytics"]
            if "total_activities" in perf:
                logger.info(f"🏃 Total Activities: {perf['total_activities'].get('value', 0)}")
                logger.info(f"📏 Total Distance: {perf['total_distance'].get('value', 0):.2f} m")
                logger.info(f"🔥 Total Calories: {perf['total_calories'].get('value', 0)}")
        else:
            logger.error(f"❌ Analytics generation failed: {analytics['error']}")
        
        # 系統統計
        logger.info("\n" + "=" * 80)
        logger.info("🖥️ System Statistics")
        logger.info("=" * 80)
        
        sys_stats = platform.get_system_stats()
        if "error" not in sys_stats:
            for data_type, stats in sys_stats["system_stats"].items():
                if stats:
                    logger.info(f"{data_type.upper()}:")
                    logger.info(f"  📄 Documents: {stats.get('document_count', 0)}")
                    logger.info(f"  💾 Size: {stats.get('index_size_mb', 0)} MB")
        else:
            logger.error(f"❌ System stats failed: {sys_stats['error']}")
    
    else:
        logger.error(f"❌ FIT file not found: {fit_file_path}")


if __name__ == "__main__":
    main()
