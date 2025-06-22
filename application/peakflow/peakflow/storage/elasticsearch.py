#!/usr/bin/env python3
"""
Elasticsearch storage implementation - implements StorageInterface
"""
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from .interface import (
    StorageInterface, DataType, QueryFilter, AggregationQuery, 
    IndexingResult, StorageError
)
from ..utils import get_logger


logger = get_logger(__name__)


class ElasticsearchStorage(StorageInterface):
    """Elasticsearch storage implementation"""
    
    def __init__(self):
        self.es: Optional[Elasticsearch] = None
        self.index_mappings = self._get_index_mappings()
        self.index_names = {
            DataType.SESSION: "fitness-sessions",
            DataType.RECORD: "fitness-records",
            DataType.LAP: "fitness-laps",
            DataType.USER_INDICATOR: "user-indicators"  # New index for user personal metrics
        }
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Elasticsearch connection"""
        try:
            # Ensure hosts include scheme
            hosts = config.get('hosts', ['http://localhost:9200'])
            if isinstance(hosts, list):
                hosts = [host if host.startswith(('http://', 'https://')) 
                        else f"http://{host}" for host in hosts]
            
            es_config = {
                'hosts': hosts,
                'request_timeout': config.get('timeout', 30),
                'max_retries': config.get('max_retries', 3),
                'retry_on_timeout': config.get('retry_on_timeout', True),
                'verify_certs': config.get('verify_certs', False)
            }
            
            # If authentication info is provided, use new basic_auth parameter
            # Only use auth if both username and password are provided
            if 'username' in config and 'password' in config and config['username'] and config['password']:
                es_config['basic_auth'] = (config['username'], config['password'])
            elif 'http_auth' in config and config['http_auth']:
                # Backward compatibility
                es_config['basic_auth'] = config['http_auth']
            
            self.es = Elasticsearch(**es_config)
            
            # Test connection
            if not self.es.ping():
                raise StorageError("Cannot connect to Elasticsearch")
            
            # Get cluster information
            cluster_info = self.es.info()
            logger.info(f"✅ Connected to Elasticsearch cluster: {cluster_info['cluster_name']}")
            logger.info(f"📊 Version: {cluster_info['version']['number']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Elasticsearch: {e}")
            raise StorageError(f"Elasticsearch initialization failed: {e}")
    
    def create_indices(self, force_recreate: bool = False) -> bool:
        """Create Elasticsearch indices"""
        try:
            for data_type, index_name in self.index_names.items():
                if self.es.indices.exists(index=index_name):
                    if force_recreate:
                        self.es.indices.delete(index=index_name)
                        logger.info(f"🗑️ Deleted existing index: {index_name}")
                    else:
                        logger.info(f"📋 Index already exists: {index_name}")
                        continue
                
                mapping = self.index_mappings[data_type]
                self.es.indices.create(index=index_name, **mapping)  # Use ** unpacking instead of body
                logger.info(f"✅ Created index: {index_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create indices: {e}")
            raise StorageError(f"Index creation failed: {e}")
    
    def index_document(self, data_type: DataType, doc_id: str, document: Dict[str, Any]) -> bool:
        """Index a single document"""
        try:
            index_name = self.index_names[data_type]
            document['indexed_at'] = datetime.now().isoformat()
            
            response = self.es.index(
                index=index_name,
                id=doc_id,
                document=document  # New version uses document instead of body
            )
            
            return response['result'] in ['created', 'updated']
            
        except Exception as e:
            logger.error(f"❌ Failed to index document {doc_id}: {e}")
            return False
    
    def bulk_index(self, data_type: DataType, documents: List[Dict[str, Any]]) -> IndexingResult:
        """Bulk index documents"""
        result = IndexingResult()
        
        try:
            index_name = self.index_names[data_type]
            
            # Prepare documents for bulk indexing
            bulk_docs = []
            for doc in documents:
                doc['indexed_at'] = datetime.now().isoformat()
                
                bulk_doc = {
                    "_index": index_name,
                    "_id": doc.get('_id', None),  # If ID is specified
                    "_source": doc
                }
                
                # Remove _id from source
                if '_id' in bulk_doc["_source"]:
                    del bulk_doc["_source"]['_id']
                
                bulk_docs.append(bulk_doc)
            
            # Execute bulk indexing
            es_with_options = self.es.options(request_timeout=60)
            success_count, failed_items = bulk(
                es_with_options, 
                bulk_docs, 
                chunk_size=1000,
                max_chunk_bytes=10485760  # 10MB
            )
            
            result.add_success(success_count)
            
            if failed_items:
                result.add_failure(len(failed_items), f"Bulk indexing had {len(failed_items)} failures")
                for item in failed_items:
                    logger.warning(f"Failed item: {item}")
            
            logger.info(f"✅ Bulk indexed {success_count} documents to {index_name}")
            
        except Exception as e:
            error_msg = f"Bulk indexing failed: {e}"
            logger.error(f"❌ {error_msg}")
            result.add_failure(len(documents), error_msg)
        
        return result
    
    def search(self, data_type: DataType, query_filter: QueryFilter) -> List[Dict[str, Any]]:
        """Search documents"""
        try:
            index_name = self.index_names[data_type]
            query = self._build_search_query(query_filter)
            
            response = self.es.search(
                index=index_name,
                **query,  # Use ** unpacking instead of body
                size=query_filter.limit,
                from_=query_filter.offset
            )
            
            return [hit['_source'] for hit in response['hits']['hits']]
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            raise StorageError(f"Search failed: {e}")
    
    def aggregate(self, data_type: DataType, query_filter: QueryFilter, 
                  agg_query: AggregationQuery) -> Dict[str, Any]:
        """Aggregation query"""
        try:
            index_name = self.index_names[data_type]
            query = self._build_search_query(query_filter)
            
            # Add aggregations
            query['aggs'] = self._build_aggregations(agg_query)
            query['size'] = 0  # Don't return documents, only aggregation results
            
            response = self.es.search(index=index_name, **query)  # Use ** unpacking
            return response.get('aggregations', {})
            
        except Exception as e:
            logger.error(f"❌ Aggregation failed: {e}")
            raise StorageError(f"Aggregation failed: {e}")
    
    def get_by_id(self, data_type: DataType, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            index_name = self.index_names[data_type]
            response = self.es.get(index=index_name, id=doc_id)
            return response['_source']
            
        except Exception as e:
            if "not_found" in str(e).lower():
                return None
            logger.error(f"❌ Get by ID failed: {e}")
            raise StorageError(f"Get by ID failed: {e}")
    
    def delete_by_id(self, data_type: DataType, doc_id: str) -> bool:
        """Delete document by ID"""
        try:
            index_name = self.index_names[data_type]
            response = self.es.delete(index=index_name, id=doc_id)
            return response['result'] == 'deleted'
            
        except Exception as e:
            if "not_found" in str(e).lower():
                return False
            logger.error(f"❌ Delete by ID failed: {e}")
            return False
    
    def delete_by_query(self, data_type: DataType, query_filter: QueryFilter) -> int:
        """Delete documents by query conditions"""
        try:
            index_name = self.index_names[data_type]
            query = self._build_search_query(query_filter)
            
            response = self.es.delete_by_query(index=index_name, **query)  # Use ** unpacking
            return response.get('deleted', 0)
            
        except Exception as e:
            logger.error(f"❌ Delete by query failed: {e}")
            raise StorageError(f"Delete by query failed: {e}")
    
    def get_stats(self, data_type: DataType) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            index_name = self.index_names[data_type]
            
            # Check if index exists
            if not self.es.indices.exists(index=index_name):
                return {
                    'document_count': 0,
                    'index_size_bytes': 0,
                    'index_size_mb': 0,
                    'shards': 0,
                    'last_updated': datetime.now().isoformat()
                }
            
            # Get document count (this should work without security issues)
            try:
                count_response = self.es.count(index=index_name)
                document_count = count_response['count']
            except Exception as count_e:
                logger.warning(f"Could not get document count: {count_e}")
                document_count = 0
            
            # Try to get detailed stats, but handle security exceptions gracefully
            try:
                stats = self.es.indices.stats(index=index_name)
                
                # Check statistics results
                if 'indices' not in stats or index_name not in stats['indices']:
                    logger.warning(f"No detailed stats found for index: {index_name}")
                    return {
                        'document_count': document_count,
                        'index_size_bytes': 0,
                        'index_size_mb': 0,
                        'shards': 0,
                        'last_updated': datetime.now().isoformat()
                    }
                
                index_stats = stats['indices'][index_name]
                
                # Safely get statistics data
                total_stats = index_stats.get('total', {})
                store_stats = total_stats.get('store', {})
                size_bytes = store_stats.get('size_in_bytes', 0)
                shards_info = total_stats.get('shards', {})
                
                return {
                    'document_count': document_count,
                    'index_size_bytes': size_bytes,
                    'index_size_mb': round(size_bytes / 1024 / 1024, 2) if size_bytes else 0,
                    'shards': shards_info.get('total', 0),
                    'last_updated': datetime.now().isoformat()
                }
                
            except Exception as stats_e:
                # Handle security exceptions or other issues with detailed stats
                if "security_exception" in str(stats_e) or "AuthorizationException" in str(stats_e):
                    logger.warning(f"Security restrictions prevent detailed stats access: {stats_e}")
                    return {
                        'document_count': document_count,
                        'index_size_bytes': 0,
                        'index_size_mb': 0,
                        'shards': 0,
                        'security_limited': True,
                        'message': 'Limited stats due to security restrictions',
                        'last_updated': datetime.now().isoformat()
                    }
                else:
                    logger.warning(f"Could not get detailed stats: {stats_e}")
                    return {
                        'document_count': document_count,
                        'index_size_bytes': 0,
                        'index_size_mb': 0,
                        'shards': 0,
                        'error': str(stats_e),
                        'last_updated': datetime.now().isoformat()
                    }
            
        except Exception as e:
            logger.error(f"❌ Get stats failed: {e}")
            return {
                'document_count': 0,
                'index_size_bytes': 0,
                'index_size_mb': 0,
                'shards': 0,
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
    
    def _build_search_query(self, query_filter: QueryFilter) -> Dict[str, Any]:
        """Build search query"""
        query = {
            "query": {
                "bool": {
                    "must": []
                }
            }
        }
        
        # Add term filters
        for field, value in query_filter.filters.items():
            query["query"]["bool"]["must"].append({
                "term": {field: value}
            })
        
        # Add date range filters
        for field, date_range in query_filter.date_range.items():
            range_query = {"range": {field: {}}}
            if date_range["start"]:
                range_query["range"][field]["gte"] = date_range["start"].isoformat()
            if date_range["end"]:
                range_query["range"][field]["lte"] = date_range["end"].isoformat()
            query["query"]["bool"]["must"].append(range_query)
        
        # Add geo bounding box filter
        if query_filter.geo_bounds:
            query["query"]["bool"]["must"].append({
                "geo_bounding_box": {
                    "location": query_filter.geo_bounds
                }
            })
        
        # Add sorting
        if query_filter.sort_fields:
            query["sort"] = []
            for sort_field in query_filter.sort_fields:
                sort_order = "asc" if sort_field["ascending"] else "desc"
                query["sort"].append({sort_field["field"]: {"order": sort_order}})
        
        # If no conditions, use match_all
        if not query["query"]["bool"]["must"]:
            query["query"] = {"match_all": {}}
        
        return query
    
    def _build_aggregations(self, agg_query: AggregationQuery) -> Dict[str, Any]:
        """Build aggregation query"""
        aggs = {}
        
        for name, agg_config in agg_query.aggs.items():
            if agg_config["type"] == "metric":
                aggs[name] = {
                    agg_config["metric"]: {"field": agg_config["field"]}
                }
            elif agg_config["type"] == "terms":
                aggs[name] = {
                    "terms": {
                        "field": agg_config["field"],
                        "size": agg_config["size"]
                    }
                }
            elif agg_config["type"] == "date_histogram":
                aggs[name] = {
                    "date_histogram": {
                        "field": agg_config["field"],
                        "calendar_interval": agg_config["interval"]
                    }
                }
        
        return aggs
    
    def _get_index_mappings(self) -> Dict[DataType, Dict[str, Any]]:
        """Get index mapping definitions"""
        return {
            DataType.SESSION: {
                "mappings": {
                    "properties": {
                        # === Basic Information ===
                        "activity_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "start_time": {"type": "date"},
                        "indexed_at": {"type": "date"},
                        
                        # === Session Main Fields ===
                        "sport": {"type": "keyword"},
                        "sub_sport": {"type": "keyword"},
                        "total_timer_time": {"type": "float"},
                        "total_elapsed_time": {"type": "float"},
                        "total_distance": {"type": "float"},
                        "total_calories": {"type": "integer"},
                        "avg_heart_rate": {"type": "integer"},
                        "max_heart_rate": {"type": "integer"},
                        "enhanced_avg_speed": {"type": "float"},
                        "enhanced_max_speed": {"type": "float"},
                        "total_ascent": {"type": "float"},
                        "total_descent": {"type": "float"},
                        "avg_cadence": {"type": "integer"},
                        "max_cadence": {"type": "integer"},
                        "total_strides": {"type": "integer"},
                        "intensity": {"type": "keyword"},
                        "activity_type": {"type": "keyword"},
                        "manufacturer": {"type": "keyword"},
                        "product": {"type": "keyword"},
                        
                        # === GPS Start Location ===
                        "start_location": {
                            "type": "geo_point",
                            "ignore_malformed": True
                        },
                        
                        # === Running Dynamics Statistics ===
                        "running_dynamics": {
                            "properties": {
                                "avg_vertical_oscillation": {"type": "float"},
                                "avg_stance_time": {"type": "float"},
                                "avg_step_length": {"type": "float"},
                                "avg_vertical_ratio": {"type": "float"},
                                "avg_ground_contact_time": {"type": "float"},
                                "stance_time_percent": {"type": "float"},
                                "vertical_oscillation_percent": {"type": "float"}
                            }
                        },
                        
                        # === Power Statistics ===
                        "power_fields": {
                            "properties": {
                                "avg_power": {"type": "integer"},
                                "max_power": {"type": "integer"},
                                "normalized_power": {"type": "integer"},
                                "functional_threshold_power": {"type": "integer"},
                                "training_stress_score": {"type": "float"},
                                "left_right_balance": {"type": "float"},
                                "avg_left_torque_effectiveness": {"type": "float"},
                                "avg_right_torque_effectiveness": {"type": "float"},
                                "avg_combined_pedal_smoothness": {"type": "float"}
                            }
                        },
                        
                        # === Heart Rate Metrics ===
                        "heart_rate_metrics": {
                            "properties": {
                                "time_in_hr_zone_1": {"type": "float"},
                                "time_in_hr_zone_2": {"type": "float"},
                                "time_in_hr_zone_3": {"type": "float"},
                                "time_in_hr_zone_4": {"type": "float"},
                                "time_in_hr_zone_5": {"type": "float"}
                            }
                        },
                        
                        # === Speed Metrics ===
                        "speed_metrics": {
                            "properties": {
                                "avg_speed": {"type": "float"},
                                "max_speed": {"type": "float"},
                                "enhanced_avg_speed": {"type": "float"},
                                "enhanced_max_speed": {"type": "float"}
                            }
                        },
                        
                        # === Environmental Data ===
                        "environmental": {
                            "properties": {
                                "avg_temperature": {"type": "float"},
                                "max_temperature": {"type": "float"},
                                "min_temperature": {"type": "float"},
                                "humidity": {"type": "float"},
                                "pressure": {"type": "float"},
                                "wind_speed": {"type": "float"},
                                "wind_direction": {"type": "float"}
                            }
                        },
                        
                        # === Swimming Fields ===
                        "swimming_fields": {
                            "properties": {
                                "pool_length": {"type": "float"},
                                "lengths": {"type": "integer"},
                                "stroke_count": {"type": "integer"},
                                "avg_strokes": {"type": "float"},
                                "avg_swolf": {"type": "integer"}
                            }
                        },
                        
                        # === Zone Fields ===
                        "zone_fields": {
                            "properties": {
                                "sport_index": {"type": "integer"},
                                "time_in_power_zone_1": {"type": "float"},
                                "time_in_power_zone_2": {"type": "float"},
                                "time_in_power_zone_3": {"type": "float"},
                                "time_in_power_zone_4": {"type": "float"},
                                "time_in_power_zone_5": {"type": "float"},
                                "time_in_power_zone_6": {"type": "float"}
                            }
                        },
                        
                        # === Additional Dynamic Fields ===
                        "additional_fields": {
                            "type": "object",
                            "dynamic": True
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "30s"
                }
            },
            
            DataType.RECORD: {
                "mappings": {
                    "properties": {
                        # === Basic Information ===
                        "activity_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "sequence": {"type": "integer"},
                        "timestamp": {"type": "date"},
                        "indexed_at": {"type": "date"},
                        
                        # === GPS Location ===
                        "location": {
                            "type": "geo_point",
                            "ignore_malformed": True
                        },
                        "gps_accuracy": {"type": "float"},
                        
                        # === Record Main Fields ===
                        "elapsed_time": {"type": "float"},
                        "distance": {"type": "float"},
                        "speed": {"type": "float"},
                        "enhanced_speed": {"type": "float"},
                        "altitude": {"type": "float"},
                        "enhanced_altitude": {"type": "float"},
                        "heart_rate": {"type": "integer"},
                        "cadence": {"type": "integer"},
                        "power": {"type": "integer"},
                        "temperature": {"type": "float"},
                        "grade": {"type": "float"},
                        "resistance": {"type": "float"},
                        
                        # === Running Dynamics Data ===
                        "running_dynamics": {
                            "properties": {
                                "vertical_oscillation": {"type": "float"},
                                "stance_time": {"type": "float"},
                                "step_length": {"type": "float"},
                                "vertical_ratio": {"type": "float"},
                                "ground_contact_time": {"type": "float"},
                                "form_power": {"type": "integer"},
                                "leg_spring_stiffness": {"type": "float"},
                                "stance_time_percent": {"type": "float"},
                                "vertical_oscillation_percent": {"type": "float"}
                            }
                        },
                        
                        # === Power Data ===
                        "power_fields": {
                            "properties": {
                                "power": {"type": "integer"},
                                "left_power": {"type": "integer"},
                                "right_power": {"type": "integer"},
                                "left_right_balance": {"type": "float"},
                                "left_torque_effectiveness": {"type": "float"},
                                "right_torque_effectiveness": {"type": "float"},
                                "left_pedal_smoothness": {"type": "float"},
                                "right_pedal_smoothness": {"type": "float"},
                                "combined_pedal_smoothness": {"type": "float"}
                            }
                        },
                        
                        # === Cycling Fields ===
                        "cycling_fields": {
                            "properties": {
                                "left_pco": {"type": "integer"},
                                "right_pco": {"type": "integer"},
                                "left_power_phase": {"type": "float"},
                                "right_power_phase": {"type": "float"},
                                "left_power_phase_peak": {"type": "float"},
                                "right_power_phase_peak": {"type": "float"},
                                "gear_change_data": {"type": "integer"}
                            }
                        },
                        
                        # === Environmental Data ===
                        "environmental": {
                            "properties": {
                                "temperature": {"type": "float"},
                                "humidity": {"type": "float"},
                                "pressure": {"type": "float"},
                                "wind_speed": {"type": "float"},
                                "wind_direction": {"type": "float"},
                                "air_pressure": {"type": "float"},
                                "barometric_pressure": {"type": "float"}
                            }
                        },
                        
                        # === Swimming Fields ===
                        "swimming_fields": {
                            "properties": {
                                "stroke_count": {"type": "integer"},
                                "strokes": {"type": "integer"},
                                "swim_stroke": {"type": "keyword"}
                            }
                        },
                        
                        # === Zone Fields ===
                        "zone_fields": {
                            "properties": {
                                "hr_zone": {"type": "integer"},
                                "power_zone": {"type": "integer"},
                                "pace_zone": {"type": "integer"},
                                "cadence_zone": {"type": "integer"}
                            }
                        },
                        
                        # === Heart Rate Metrics ===
                        "heart_rate_metrics": {
                            "properties": {
                                "max_heart_rate": {"type": "integer"},
                                "min_heart_rate": {"type": "integer"},
                                "avg_heart_rate": {"type": "integer"}
                            }
                        },
                        
                        # === Speed Metrics ===
                        "speed_metrics": {
                            "properties": {
                                "max_speed": {"type": "float"},
                                "min_speed": {"type": "float"},
                                "avg_speed": {"type": "float"}
                            }
                        },
                        
                        # === Cadence Metrics ===
                        "cadence_metrics": {
                            "properties": {
                                "max_cadence": {"type": "integer"},
                                "min_cadence": {"type": "integer"},
                                "avg_cadence": {"type": "integer"}
                            }
                        },
                        
                        # === Additional Dynamic Fields ===
                        "additional_fields": {
                            "type": "object",
                            "dynamic": True
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "5s",
                    "index.max_result_window": 100000
                }
            },
            
            DataType.LAP: {
                "mappings": {
                    "properties": {
                        # === Basic Information ===
                        "activity_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "lap_number": {"type": "integer"},
                        "timestamp": {"type": "date"},
                        "start_time": {"type": "date"},
                        "indexed_at": {"type": "date"},
                        
                        # === Lap Main Fields ===
                        "total_distance": {"type": "float"},
                        "total_timer_time": {"type": "float"},
                        "total_elapsed_time": {"type": "float"},
                        "avg_heart_rate": {"type": "integer"},
                        "max_heart_rate": {"type": "integer"},
                        "enhanced_avg_speed": {"type": "float"},
                        "enhanced_max_speed": {"type": "float"},
                        "avg_cadence": {"type": "integer"},
                        "max_cadence": {"type": "integer"},
                        "total_calories": {"type": "integer"},
                        "total_strides": {"type": "integer"},
                        "lap_trigger": {"type": "keyword"},
                        "intensity": {"type": "keyword"},
                        "total_ascent": {"type": "float"},
                        "total_descent": {"type": "float"},
                        
                        # === GPS Start/End Location ===
                        "start_location": {
                            "type": "geo_point",
                            "ignore_malformed": True
                        },
                        "end_location": {
                            "type": "geo_point",
                            "ignore_malformed": True
                        },
                        
                        # === Running Dynamics Statistics ===
                        "running_dynamics": {
                            "properties": {
                                "avg_vertical_oscillation": {"type": "float"},
                                "avg_stance_time": {"type": "float"},
                                "avg_step_length": {"type": "float"},
                                "avg_vertical_ratio": {"type": "float"},
                                "avg_ground_contact_time": {"type": "float"},
                                "stance_time_percent": {"type": "float"},
                                "vertical_oscillation_percent": {"type": "float"}
                            }
                        },
                        
                        # === Power Statistics ===
                        "power_fields": {
                            "properties": {
                                "avg_power": {"type": "integer"},
                                "max_power": {"type": "integer"},
                                "normalized_power": {"type": "integer"},
                                "left_right_balance": {"type": "float"},
                                "avg_left_torque_effectiveness": {"type": "float"},
                                "avg_right_torque_effectiveness": {"type": "float"},
                                "avg_combined_pedal_smoothness": {"type": "float"}
                            }
                        },
                        
                        # === Heart Rate Metrics ===
                        "heart_rate_metrics": {
                            "properties": {
                                "time_in_hr_zone_1": {"type": "float"},
                                "time_in_hr_zone_2": {"type": "float"},
                                "time_in_hr_zone_3": {"type": "float"},
                                "time_in_hr_zone_4": {"type": "float"},
                                "time_in_hr_zone_5": {"type": "float"}
                            }
                        },
                        
                        # === Speed Metrics ===
                        "speed_metrics": {
                            "properties": {
                                "avg_speed": {"type": "float"},
                                "max_speed": {"type": "float"},
                                "min_speed": {"type": "float"}
                            }
                        },
                        
                        # === Environmental Data ===
                        "environmental": {
                            "properties": {
                                "avg_temperature": {"type": "float"},
                                "max_temperature": {"type": "float"},
                                "min_temperature": {"type": "float"},
                                "humidity": {"type": "float"},
                                "pressure": {"type": "float"}
                            }
                        },
                        
                        # === Swimming Fields ===
                        "swimming_fields": {
                            "properties": {
                                "pool_length": {"type": "float"},
                                "lengths": {"type": "integer"},
                                "stroke_count": {"type": "integer"},
                                "avg_strokes": {"type": "float"},
                                "avg_swolf": {"type": "integer"}
                            }
                        },
                        
                        # === Cycling Fields ===
                        "cycling_fields": {
                            "properties": {
                                "avg_left_pco": {"type": "integer"},
                                "avg_right_pco": {"type": "integer"},
                                "avg_left_power_phase": {"type": "float"},
                                "avg_right_power_phase": {"type": "float"}
                            }
                        },
                        
                        # === Zone Fields ===
                        "zone_fields": {
                            "properties": {
                                "sport_index": {"type": "integer"},
                                "time_in_power_zone_1": {"type": "float"},
                                "time_in_power_zone_2": {"type": "float"},
                                "time_in_power_zone_3": {"type": "float"},
                                "time_in_power_zone_4": {"type": "float"},
                                "time_in_power_zone_5": {"type": "float"},
                                "time_in_power_zone_6": {"type": "float"}
                            }
                        },
                        
                        # === Additional Dynamic Fields ===
                        "additional_fields": {
                            "type": "object",
                            "dynamic": True
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "10s"
                }
            },
            
            DataType.USER_INDICATOR: {
                "mappings": {
                    "properties": {
                        "user_id": {"type": "keyword"},
                        "threshold_heart_rate": {"type": "integer"},
                        "threshold_power": {"type": "integer"},
                        "threshold_pace": {"type": "float"},
                        "vo2max": {"type": "float"},
                        "max_heart_rate": {"type": "integer"},
                        "resting_heart_rate": {"type": "integer"},
                        "training_stress_score": {"type": "float"},
                        "critical_power": {"type": "integer"},
                        "critical_speed": {"type": "float"},
                        "anaerobic_threshold": {"type": "float"},
                        "aerobic_threshold": {"type": "float"},
                        "max_power": {"type": "integer"},
                        "max_pace": {"type": "float"},
                        "weight": {"type": "float"},
                        "height": {"type": "float"},
                        "gender": {"type": "keyword"},
                        "age": {"type": "integer"},
                        "training_zones": {"type": "object", "dynamic": True},
                        "vdot": {"type": "float"},
                        "running_economy": {"type": "float"},
                        "cycling_efficiency": {"type": "float"},
                        "stride_length": {"type": "float"},
                        "cadence": {"type": "float"},
                        "power_to_weight_ratio": {"type": "float"},
                        "body_fat_percentage": {"type": "float"},
                        "muscle_mass": {"type": "float"},
                        "hydration_level": {"type": "float"},
                        "sleep_quality": {"type": "float"},
                        "recovery_time": {"type": "float"},
                        "training_load": {"type": "float"},
                        "fitness_score": {"type": "float"},
                        "fatigue_score": {"type": "float"},
                        "form_score": {"type": "float"},
                        "updated_at": {"type": "date"},
                        "created_at": {"type": "date"},
                        "additional_fields": {"type": "object", "dynamic": True}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "10s"
                }
            }
        }
