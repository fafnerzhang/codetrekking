#!/usr/bin/env python3
"""
Garmin FIT File Processing DAG

This DAG processes FIT files by:
1. Parsing FIT files using processors/fit module
2. Validating data using Pydantic models from storage/model.py
3. Saving raw data to Elasticsearch

Can run after download_task or be triggered independently with user name and FIT file IDs.
"""

from airflow.sdk import DAG, task, Param
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from airflow.models import Variable
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from peakflow.storage.elasticsearch import ElasticsearchStorage
from peakflow.storage.interface import DataType, QueryFilter
from peakflow.const import ELASTICSEARCH_HOST, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD
import os
import logging


# Define default parameters
default_params = {
    'user': Param(
        default='example@gmail.com',
        type='string',
        title='Garmin Connect Username',
        description='Your Garmin Connect account username'
    ),
    'fit_file_ids': Param(
        default=[],
        type='array',
        title='FIT File IDs',
        description='List of FIT file IDs to process (can be activity IDs or file names). Leave empty to process all new files from download task.'
    ),
    'source_directory': Param(
        default='',
        type='string', 
        title='Source Directory',
        description='Directory to search for FIT files (optional). If empty, uses default Garmin directory for user.'
    ),
    'validate_with_pydantic': Param(
        default=True,
        type='boolean',
        title='Validate with Pydantic Models',
        description='Whether to validate data using Pydantic models before saving to Elasticsearch'
    ),
    'overwrite_existing': Param(
        default=False,
        type='boolean', 
        title='Overwrite Existing Data',
        description='Whether to overwrite existing data in Elasticsearch'
    ),
    'batch_size': Param(
        default=1000,
        type='integer',
        minimum=100,
        maximum=5000,
        title='Batch Size',
        description='Number of records to process in each batch for Elasticsearch indexing'
    )
}

"""
This DAG uses ExternalTaskSensor to wait for the completion of the 'download_garmin_daily_data' task
in the 'garmin_download_daily_data' DAG before starting FIT file processing.
Sensor reference: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html
"""

# Create DAG
with DAG(
    dag_id='garmin_process_fit_files',
    description='Process Garmin FIT files with validation and save to Elasticsearch',
    schedule=None,  # Manual trigger or triggered by other DAGs
    start_date=datetime(2025, 6, 1),
    catchup=False,
    tags=['garmin', 'fit', 'processing', 'elasticsearch', 'peakflow'],
    params=default_params,
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
    },
    render_template_as_native_obj=True,
) as dag:

    @task.python(task_id='discover_fit_files')
    def discover_fit_files(**context) -> Dict[str, Any]:
        """
        Discover FIT files to process based on parameters
        
        Returns:
            dict: Information about discovered FIT files
        """
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        fit_file_ids = params.get('fit_file_ids', [])
        source_directory = params.get('source_directory', '')
        
        # If downstream task result is available (from download DAG), use it
        downstream_result = context.get('task_instance', {}).xcom_pull(
            task_ids='download_garmin_daily_data', 
            dag_id='garmin_download_daily_data',
            default=None
        )
        
        discovered_files = []
        
        print(f"🔍 Discovering FIT files for user: {user}")
        
        # Method 1: Use specific FIT file IDs if provided
        if fit_file_ids:
            print(f"📋 Processing specific FIT file IDs: {fit_file_ids}")
            
            # Default search directory
            if not source_directory:
                source_directory = f"/opt/garmin/{user}"
            
            source_path = Path(source_directory)
            if not source_path.exists():
                print(f"❌ Source directory does not exist: {source_directory}")
                return {
                    'status': 'error',
                    'error': f'Source directory does not exist: {source_directory}',
                    'discovered_files': [],
                    'user': user
                }
            
            # Look for FIT files matching the IDs
            for fit_id in fit_file_ids:
                # Try different file patterns
                patterns = [
                    f"{fit_id}.fit",
                    f"{fit_id}_ACTIVITY.fit", 
                    f"*{fit_id}*.fit"
                ]
                
                found = False
                for pattern in patterns:
                    matching_files = list(source_path.rglob(pattern))
                    for file_path in matching_files:
                        if file_path.suffix.lower() == '.fit':
                            discovered_files.append({
                                'file_path': str(file_path),
                                'file_name': file_path.name,
                                'activity_id': fit_id,
                                'file_size': file_path.stat().st_size,
                                'modified_time': file_path.stat().st_mtime
                            })
                            found = True
                            break
                    if found:
                        break
                
                if not found:
                    print(f"⚠️ FIT file not found for ID: {fit_id}")
        
        # Method 2: Use results from download task
        elif downstream_result and downstream_result.get('status') == 'success':
            print("📥 Using FIT files from download task")
            
            # Try to use enhanced file_details first (new format)
            file_details = downstream_result.get('file_details', [])
            if file_details:
                print(f"✅ Using enhanced file metadata from download task ({len(file_details)} files)")
                for file_detail in file_details:
                    if Path(file_detail['file_path']).exists():
                        discovered_files.append({
                            'file_path': file_detail['file_path'],
                            'file_name': file_detail['file_name'],
                            'activity_id': file_detail['activity_id'],
                            'file_size': file_detail['file_size'],
                            'modified_time': file_detail['modified_time']
                        })
                    else:
                        print(f"⚠️ File not found: {file_detail['file_path']}")
            else:
                # Fallback to legacy format
                print("📂 Using legacy downloaded_fit_files format")
                downloaded_files = downstream_result.get('downloaded_fit_files', [])
                
                for file_path in downloaded_files:
                    path_obj = Path(file_path)
                    if path_obj.exists() and path_obj.suffix.lower() == '.fit':
                        # Extract activity ID from filename
                        activity_id = path_obj.stem
                        if '_ACTIVITY' in activity_id:
                            activity_id = activity_id.replace('_ACTIVITY', '')
                        
                        discovered_files.append({
                            'file_path': str(path_obj),
                            'file_name': path_obj.name,
                            'activity_id': activity_id,
                            'file_size': path_obj.stat().st_size,
                            'modified_time': path_obj.stat().st_mtime
                        })
        
        # Method 3: Discover all FIT files in directory
        else:
            print("🔎 Discovering all FIT files in directory")
            
            if not source_directory:
                source_directory = f"/opt/garmin/{user}"
            
            source_path = Path(source_directory)
            if source_path.exists():
                for fit_file in source_path.rglob("*.fit"):
                    activity_id = fit_file.stem
                    if '_ACTIVITY' in activity_id:
                        activity_id = activity_id.replace('_ACTIVITY', '')
                    
                    discovered_files.append({
                        'file_path': str(fit_file),
                        'file_name': fit_file.name,
                        'activity_id': activity_id,
                        'file_size': fit_file.stat().st_size,
                        'modified_time': fit_file.stat().st_mtime
                    })
            else:
                print(f"⚠️ Source directory does not exist: {source_directory}")
        
        # Sort by modification time (newest first)
        discovered_files.sort(key=lambda x: x['modified_time'], reverse=True)
        
        result = {
            'status': 'success',
            'user': user,
            'source_directory': source_directory,
            'discovered_files': discovered_files,
            'total_files': len(discovered_files),
            'discovery_method': 'specific_ids' if fit_file_ids else ('download_task' if downstream_result else 'directory_scan')
        }
        
        print(f"✅ Discovered {len(discovered_files)} FIT files")
        for i, file_info in enumerate(discovered_files[:5]):  # Show first 5
            print(f"  {i+1}. {file_info['file_name']} (Activity: {file_info['activity_id']}, Size: {file_info['file_size']} bytes)")
        
        if len(discovered_files) > 5:
            print(f"  ... and {len(discovered_files) - 5} more files")
        
        return result

    @task.python(task_id='process_fit_files')
    def process_fit_files(discovery_result: Dict[str, Any], **context) -> Dict[str, Any]:
        """
        Process discovered FIT files using processors/fit module
        
        Args:
            discovery_result: Result from discover_fit_files task
            
        Returns:
            dict: Processing results
        """
        if not discovery_result or discovery_result.get('status') != 'success':
            return {'status': 'error', 'error': 'No files discovered or discovery failed'}
        
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        validate_with_pydantic = params.get('validate_with_pydantic', True)
        batch_size = params.get('batch_size', 1000)
        
        discovered_files = discovery_result.get('discovered_files', [])
        
        if not discovered_files:
            return {
                'status': 'completed',
                'message': 'No FIT files to process',
                'user': user,
                'processed_files': 0
            }
        
        print(f"🔄 Starting FIT file processing for {len(discovered_files)} files")
        
        try:
            # Import PeakFlow modules
            from peakflow.processors.fit import FitFileProcessor
            from peakflow.processors.interface import ProcessingOptions
            from peakflow.storage.elasticsearch import ElasticsearchStorage
            from peakflow.storage.interface import DataType
            
            if validate_with_pydantic:
                from peakflow.storage.model import SessionModel, RecordModel, LapModel
                print("✅ Pydantic models loaded for validation")
            
        except ImportError as e:
            error_msg = f"Failed to import PeakFlow modules: {e}"
            print(f"❌ {error_msg}")
            return {'status': 'error', 'error': error_msg}
        
        # Initialize Elasticsearch storage
        try:
            storage = ElasticsearchStorage()
            es_config = {
                'hosts': ['http://elasticsearch:9200'],
                'username': 'elastic',
                'password': 'FAFNERji3g4',
                'verify_certs': False,
                'timeout': 60,
                'max_retries': 3
            }
            
            if not storage.initialize(es_config):
                raise Exception("Failed to initialize Elasticsearch storage")
            
            # Ensure indices exist
            storage.create_indices(force_recreate=False)
            print("✅ Elasticsearch storage initialized")
            
        except Exception as e:
            error_msg = f"Failed to initialize Elasticsearch: {e}"
            print(f"❌ {error_msg}")
            return {'status': 'error', 'error': error_msg}
        
        # Initialize FIT processor
        try:
            processing_options = ProcessingOptions(
                validate_data=True,
                skip_invalid_records=True,
                batch_size=batch_size
            )
            
            processor = FitFileProcessor(storage, processing_options)
            print("✅ FIT processor initialized")
            
        except Exception as e:
            error_msg = f"Failed to initialize FIT processor: {e}"
            print(f"❌ {error_msg}")
            return {'status': 'error', 'error': error_msg}
        
        # Process each FIT file
        processing_results = []
        total_sessions = 0
        total_records = 0
        total_laps = 0
        total_errors = 0
        
        for file_info in discovered_files:
            file_path = file_info['file_path']
            activity_id = file_info['activity_id']
            file_name = file_info['file_name']
            
            print(f"\n📁 Processing FIT file: {file_name}")
            print(f"   Path: {file_path}")
            print(f"   Activity ID: {activity_id}")
            
            try:
                # Validate FIT file
                if not processor.validate_source(file_path):
                    error_msg = f"Invalid FIT file format: {file_name}"
                    print(f"❌ {error_msg}")
                    processing_results.append({
                        'file_path': file_path,
                        'file_name': file_name,
                        'activity_id': activity_id,
                        'status': 'failed',
                        'error': error_msg
                    })
                    total_errors += 1
                    continue
                
                # Process the FIT file
                result = processor.process(file_path, user, activity_id)
                
                file_result = {
                    'file_path': file_path,
                    'file_name': file_name,
                    'activity_id': activity_id,
                    'status': result.status.value,
                    'sessions': result.metadata.get('sessions', 0),
                    'records': result.metadata.get('records', 0),
                    'laps': result.metadata.get('laps', 0),
                    'successful_records': result.successful_records,
                    'failed_records': result.failed_records,
                    'processing_time': result.processing_time,
                    'errors': result.errors if result.errors else None,
                    'warnings': result.warnings if result.warnings else None
                }
                
                # Additional Pydantic validation if requested
                if validate_with_pydantic and result.successful_records > 0:
                    print(f"   🔍 Performing additional Pydantic validation...")
                    pydantic_result = validate_with_pydantic_models(
                        storage, activity_id, user, SessionModel, RecordModel, LapModel
                    )
                    file_result['pydantic_validation'] = pydantic_result
                
                processing_results.append(file_result)
                
                # Update totals
                total_sessions += file_result['sessions']
                total_records += file_result['records'] 
                total_laps += file_result['laps']
                
                if result.status.value != 'completed':
                    total_errors += 1
                
                print(f"✅ Completed processing {file_name}:")
                print(f"   📊 Sessions: {file_result['sessions']}")
                print(f"   🏃 Records: {file_result['records']}")
                print(f"   🏁 Laps: {file_result['laps']}")
                print(f"   ✅ Success: {file_result['successful_records']}")
                print(f"   ❌ Failed: {file_result['failed_records']}")
                print(f"   ⏱️ Time: {file_result['processing_time']:.2f}s")
                
            except Exception as e:
                error_msg = f"Processing failed for {file_name}: {str(e)}"
                print(f"❌ {error_msg}")
                processing_results.append({
                    'file_path': file_path,
                    'file_name': file_name,
                    'activity_id': activity_id,
                    'status': 'failed',
                    'error': error_msg
                })
                total_errors += 1
        
        # Final summary
        successful_files = len([r for r in processing_results if r['status'] in ['completed', 'partially_completed']])
        
        final_result = {
            'status': 'completed' if total_errors == 0 else 'partially_completed',
            'user': user,
            'total_files_processed': len(discovered_files),
            'successful_files': successful_files,
            'failed_files': total_errors,
            'total_sessions': total_sessions,
            'total_records': total_records,
            'total_laps': total_laps,
            'validation_enabled': validate_with_pydantic,
            'batch_size': batch_size,
            'processing_results': processing_results,
            'summary': {
                'files_processed': len(discovered_files),
                'files_successful': successful_files,
                'files_failed': total_errors,
                'data_points_total': total_sessions + total_records + total_laps
            }
        }
        
        print(f"\n🎯 Processing Summary:")
        print(f"   📁 Files processed: {len(discovered_files)}")
        print(f"   ✅ Files successful: {successful_files}")
        print(f"   ❌ Files failed: {total_errors}")
        print(f"   📊 Total sessions: {total_sessions}")
        print(f"   🏃 Total records: {total_records}")
        print(f"   🏁 Total laps: {total_laps}")
        print(f"   📈 Total data points: {total_sessions + total_records + total_laps}")
        
        return final_result

    @task.python(task_id='validate_elasticsearch_data')
    def validate_elasticsearch_data(processing_result: Dict[str, Any], **context) -> Dict[str, Any]:
        """
        Validate that data was properly stored in Elasticsearch
        
        Args:
            processing_result: Result from process_fit_files task
            
        Returns:
            dict: Validation results
        """
        if not processing_result or processing_result.get('status') == 'error':
            return {'status': 'skipped', 'reason': 'Processing failed or no data to validate'}
        
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        
        print(f"🔍 Validating Elasticsearch data for user: {user}")
        
        try:
            es_host = Variable.get('ELASTICSEARCH_HOST', default_var=ELASTICSEARCH_HOST)
            es_user = Variable.get('ELASTICSEARCH_USERNAME', default_var=ELASTICSEARCH_USER)
            es_pass = Variable.get('ELASTICSEARCH_PASSWORD', default_var=ELASTICSEARCH_PASSWORD)
            # Initialize storage
            storage = ElasticsearchStorage()
            es_config = {
                'hosts': [es_host],
                'username': es_user,
                'password': es_pass,
                'verify_certs': False,
                'timeout': 30
            }
            
            if not storage.initialize(es_config):
                raise Exception("Failed to connect to Elasticsearch")
            
        except Exception as e:
            error_msg = f"Failed to initialize Elasticsearch for validation: {e}"
            print(f"❌ {error_msg}")
            return {'status': 'error', 'error': error_msg}
        
        validation_results = {}
        
        # Get activity IDs from processing results
        processed_activities = []
        if 'processing_results' in processing_result:
            for file_result in processing_result['processing_results']:
                if file_result.get('status') in ['completed', 'partially_completed']:
                    processed_activities.append(file_result['activity_id'])
        
        print(f"📋 Validating {len(processed_activities)} processed activities")
        
        # Validate each data type
        for data_type in [DataType.SESSION, DataType.RECORD, DataType.LAP]:
            try:
                type_name = data_type.name.lower()
                print(f"\n📊 Validating {type_name} data...")
                
                # Query for user data
                query_filter = QueryFilter()
                query_filter.add_term_filter('user_id', user)
                query_filter.limit = 10000  # Get a large sample
                
                # Search for data
                documents = storage.search(data_type, query_filter)
                
                # Filter for recently processed activities
                relevant_docs = []
                for doc in documents:
                    doc_activity_id = doc.get('activity_id')
                    if doc_activity_id in processed_activities:
                        relevant_docs.append(doc)
                
                validation_results[type_name] = {
                    'total_documents': len(documents),
                    'relevant_documents': len(relevant_docs),
                    'sample_document': relevant_docs[0] if relevant_docs else None,
                    'data_quality': analyze_data_quality(relevant_docs, data_type)
                }
                
                print(f"   ✅ {type_name.capitalize()}: {len(relevant_docs)} relevant documents out of {len(documents)} total")
                
            except Exception as e:
                print(f"   ❌ Failed to validate {type_name} data: {e}")
                validation_results[type_name] = {
                    'error': str(e),
                    'total_documents': 0,
                    'relevant_documents': 0
                }
        
        # Get storage statistics
        try:
            storage_stats = {}
            for data_type in [DataType.SESSION, DataType.RECORD, DataType.LAP]:
                stats = storage.get_stats(data_type)
                storage_stats[data_type.name.lower()] = stats
                
            validation_results['storage_stats'] = storage_stats
            
        except Exception as e:
            print(f"⚠️ Could not get storage statistics: {e}")
            validation_results['storage_stats'] = {'error': str(e)}
        
        # Overall validation status
        total_relevant = sum(v.get('relevant_documents', 0) for v in validation_results.values() if isinstance(v, dict))
        expected_minimum = len(processed_activities)  # At least one document per activity
        
        final_result = {
            'status': 'success' if total_relevant >= expected_minimum else 'warning',
            'user': user,
            'processed_activities': processed_activities,
            'total_relevant_documents': total_relevant,
            'expected_minimum_documents': expected_minimum,
            'validation_details': validation_results,
            'validation_passed': total_relevant >= expected_minimum,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"\n🎯 Validation Summary:")
        print(f"   📊 Total relevant documents: {total_relevant}")
        print(f"   📋 Expected minimum: {expected_minimum}")
        print(f"   ✅ Validation passed: {final_result['validation_passed']}")
        
        return final_result

    @task.python(task_id='generate_processing_report')
    def generate_processing_report(
        discovery_result: Dict[str, Any],
        processing_result: Dict[str, Any], 
        validation_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive processing report
        
        Args:
            discovery_result: Result from discover_fit_files task
            processing_result: Result from process_fit_files task  
            validation_result: Result from validate_elasticsearch_data task
            
        Returns:
            dict: Comprehensive report
        """
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        
        print(f"📊 Generating processing report for user: {user}")
        
        # Calculate overall success rate
        total_files = discovery_result.get('total_files', 0) if discovery_result else 0
        successful_files = processing_result.get('successful_files', 0) if processing_result else 0
        success_rate = (successful_files / total_files * 100) if total_files > 0 else 0
        
        # Aggregate data counts
        total_data_points = 0
        data_breakdown = {}
        
        if processing_result:
            total_data_points = (
                processing_result.get('total_sessions', 0) +
                processing_result.get('total_records', 0) +  
                processing_result.get('total_laps', 0)
            )
            
            data_breakdown = {
                'sessions': processing_result.get('total_sessions', 0),
                'records': processing_result.get('total_records', 0),
                'laps': processing_result.get('total_laps', 0)
            }
        
        # Validation status
        validation_passed = validation_result.get('validation_passed', False) if validation_result else False
        
        # Generate report
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'user': user,
            'dag_run_id': context.get('dag_run', {}).run_id,
            'processing_params': params,
            
            # Discovery Summary
            'discovery': {
                'status': discovery_result.get('status') if discovery_result else 'not_run',
                'files_discovered': total_files,
                'discovery_method': discovery_result.get('discovery_method') if discovery_result else 'unknown',
                'source_directory': discovery_result.get('source_directory') if discovery_result else None
            },
            
            # Processing Summary
            'processing': {
                'status': processing_result.get('status') if processing_result else 'not_run',
                'files_processed': total_files,
                'files_successful': successful_files,
                'files_failed': processing_result.get('failed_files', 0) if processing_result else 0,
                'success_rate_percent': round(success_rate, 2),
                'total_data_points': total_data_points,
                'data_breakdown': data_breakdown,
                'validation_enabled': processing_result.get('validation_enabled', False) if processing_result else False
            },
            
            # Validation Summary  
            'validation': {
                'status': validation_result.get('status') if validation_result else 'not_run',
                'validation_passed': validation_passed,
                'total_relevant_documents': validation_result.get('total_relevant_documents', 0) if validation_result else 0,
                'expected_minimum': validation_result.get('expected_minimum_documents', 0) if validation_result else 0
            },
            
            # Overall Status
            'overall_status': determine_overall_status(discovery_result, processing_result, validation_result),
            
            # Detailed Results (for debugging)
            'detailed_results': {
                'discovery_result': discovery_result,
                'processing_result': processing_result,
                'validation_result': validation_result
            }
        }
        
        # Log summary
        print(f"\n📋 PROCESSING REPORT SUMMARY")
        print(f"═══════════════════════════════════════")
        print(f"👤 User: {user}")
        print(f"🔍 Files discovered: {total_files}")
        print(f"✅ Files successful: {successful_files}")
        print(f"❌ Files failed: {report['processing']['files_failed']}")
        print(f"📊 Success rate: {success_rate:.1f}%")
        print(f"📈 Total data points: {total_data_points}")
        print(f"   - Sessions: {data_breakdown.get('sessions', 0)}")
        print(f"   - Records: {data_breakdown.get('records', 0)}")
        print(f"   - Laps: {data_breakdown.get('laps', 0)}")
        print(f"🔍 Validation passed: {validation_passed}")
        print(f"🎯 Overall status: {report['overall_status']}")
        print(f"═══════════════════════════════════════")
        
        return report

    # Helper functions (defined outside tasks)
    def validate_with_pydantic_models(storage, activity_id: str, user_id: str, 
                                    SessionModel, RecordModel, LapModel) -> Dict[str, Any]:
        """Validate data using Pydantic models"""
        try:
            from peakflow.storage.interface import DataType, QueryFilter
            
            validation_results = {
                'sessions': {'valid': 0, 'invalid': 0, 'errors': []},
                'records': {'valid': 0, 'invalid': 0, 'errors': []},
                'laps': {'valid': 0, 'invalid': 0, 'errors': []}
            }
            
            # Validate sessions
            query_filter = QueryFilter()
            query_filter.add_term_filter('activity_id', activity_id)
            query_filter.add_term_filter('user_id', user_id)
            
            sessions = storage.search(DataType.SESSION, query_filter)
            for session in sessions:
                try:
                    SessionModel(**session)
                    validation_results['sessions']['valid'] += 1
                except Exception as e:
                    validation_results['sessions']['invalid'] += 1
                    validation_results['sessions']['errors'].append(str(e))
            
            # Validate records (sample only to avoid performance issues)
            query_filter.limit = 100  # Sample first 100 records
            records = storage.search(DataType.RECORD, query_filter)
            for record in records:
                try:
                    RecordModel(**record)
                    validation_results['records']['valid'] += 1
                except Exception as e:
                    validation_results['records']['invalid'] += 1
                    validation_results['records']['errors'].append(str(e))
            
            # Validate laps
            query_filter.limit = 1000  # Reset limit for laps
            laps = storage.search(DataType.LAP, query_filter)
            for lap in laps:
                try:
                    LapModel(**lap)
                    validation_results['laps']['valid'] += 1
                except Exception as e:
                    validation_results['laps']['invalid'] += 1
                    validation_results['laps']['errors'].append(str(e))
            
            return validation_results
            
        except Exception as e:
            return {'error': f'Pydantic validation failed: {str(e)}'}

    def analyze_data_quality(documents: List[Dict], data_type) -> Dict[str, Any]:
        """Analyze data quality for documents"""
        if not documents:
            return {'quality_score': 0, 'issues': ['No documents found']}
        
        quality_issues = []
        total_fields = 0
        missing_fields = 0
        
        # Check required fields based on data type
        required_fields = {
            'SESSION': ['activity_id', 'user_id', 'timestamp'],
            'RECORD': ['activity_id', 'user_id', 'timestamp', 'sequence'],
            'LAP': ['activity_id', 'user_id', 'timestamp', 'lap_number']
        }
        
        type_name = data_type.name if hasattr(data_type, 'name') else str(data_type)
        required = required_fields.get(type_name, [])
        
        for doc in documents[:10]:  # Sample first 10 documents
            for field in required:
                total_fields += 1
                if field not in doc or doc[field] is None:
                    missing_fields += 1
        
        if missing_fields > 0:
            quality_issues.append(f'{missing_fields}/{total_fields} required fields missing')
        
        # Check for additional data quality indicators
        sample_doc = documents[0]
        if 'additional_fields' in sample_doc and sample_doc['additional_fields']:
            quality_issues.append('Additional fields present (good data coverage)')
        
        quality_score = max(0, 100 - (missing_fields / total_fields * 100) if total_fields > 0 else 100)
        
        return {
            'quality_score': round(quality_score, 2),
            'issues': quality_issues,
            'sample_size': min(len(documents), 10),
            'total_documents': len(documents)
        }

    def determine_overall_status(discovery_result, processing_result, validation_result) -> str:
        """Determine overall status based on all task results"""
        if not discovery_result or discovery_result.get('status') != 'success':
            return 'discovery_failed'
        
        if not processing_result:
            return 'processing_failed'
        
        processing_status = processing_result.get('status')
        if processing_status == 'error':
            return 'processing_failed'
        elif processing_status == 'partially_completed':
            return 'partially_successful'
        
        if validation_result and not validation_result.get('validation_passed', True):
            return 'validation_warning'
        
        return 'success'

    discovery_task = discover_fit_files()
    processing_task = process_fit_files(discovery_task)
    validation_task = validate_elasticsearch_data(processing_task)
    report_task = generate_processing_report(discovery_task, processing_task, validation_task)

    # Set task flow: wait for download, then process
    discovery_task >> processing_task >> validation_task >> report_task
