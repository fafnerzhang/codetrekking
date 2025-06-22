#!/usr/bin/env python3
"""
FIT File Data Structure Analysis and Summary
"""
import fitparse
from collections import defaultdict, Counter
import pandas as pd
from pathlib import Path


def analyze_fit_file(fit_file_path):
    """Analyze the complete structure of a FIT file"""
    
    print(f"🔍 Analyzing FIT file: {fit_file_path}")
    print("=" * 80)
    
    fit = fitparse.FitFile(fit_file_path)
    
    # Analysis results dictionary
    analysis = {
        'session': {'count': 0, 'fields': [], 'field_details': {}},
        'record': {'count': 0, 'fields': [], 'field_details': {}},
        'lap': {'count': 0, 'fields': [], 'field_details': {}}
    }
    
    # 1. Analyze Session data
    print("\n📊 Session Data Analysis")
    print("-" * 50)
    
    sessions = list(fit.get_messages('session'))
    analysis['session']['count'] = len(sessions)
    
    if sessions:
        session = sessions[0]
        for field in session.fields:
            if field.value is not None:
                field_info = {
                    'name': field.name,
                    'type': type(field.value).__name__,
                    'units': field.units or '',
                    'sample_value': str(field.value)[:50] + ('...' if len(str(field.value)) > 50 else ''),
                    'data_category': 'session'
                }
                analysis['session']['fields'].append(field.name)
                analysis['session']['field_details'][field.name] = field_info
    
    print(f"📈 Session data count: {analysis['session']['count']} records")
    print(f"🏷️  Session field count: {len(analysis['session']['fields'])} fields")
    
    # 2. Analyze Record data
    print("\n🏃 Record Data Analysis")
    print("-" * 50)
    
    records = list(fit.get_messages('record'))
    analysis['record']['count'] = len(records)
    
    # Count record field occurrence frequency
    field_frequency = {}
    for record in records:
        for field in record.fields:
            if field.value is not None:
                if field.name not in field_frequency:
                    field_frequency[field.name] = {
                        'count': 0,
                        'type': type(field.value).__name__,
                        'units': field.units or '',
                        'sample_value': str(field.value)[:50] + ('...' if len(str(field.value)) > 50 else '')
                    }
                field_frequency[field.name]['count'] += 1
    
    for field_name, info in field_frequency.items():
        field_info = {
            'name': field_name,
            'type': info['type'],
            'units': info['units'],
            'sample_value': info['sample_value'],
            'frequency': f"{info['count']}/{analysis['record']['count']}",
            'percentage': f"{info['count']/analysis['record']['count']*100:.1f}%",
            'data_category': 'record'
        }
        analysis['record']['fields'].append(field_name)
        analysis['record']['field_details'][field_name] = field_info
    
    print(f"📈 Record data count: {analysis['record']['count']} records")
    print(f"🏷️  Record field count: {len(analysis['record']['fields'])} fields")
    
    # 3. Analyze Lap data
    print("\n🏁 Lap Data Analysis")
    print("-" * 50)
    
    laps = list(fit.get_messages('lap'))
    analysis['lap']['count'] = len(laps)
    
    if laps:
        lap = laps[0]
        for field in lap.fields:
            if field.value is not None:
                field_info = {
                    'name': field.name,
                    'type': type(field.value).__name__,
                    'units': field.units or '',
                    'sample_value': str(field.value)[:50] + ('...' if len(str(field.value)) > 50 else ''),
                    'data_category': 'lap'
                }
                analysis['lap']['fields'].append(field.name)
                analysis['lap']['field_details'][field.name] = field_info
    
    print(f"📈 Lap data count: {analysis['lap']['count']} records")
    print(f"🏷️  Lap field count: {len(analysis['lap']['fields'])} fields")
    
    return analysis


def create_summary_tables(analysis):
    """Create data summary tables"""
    
    print("\n" + "=" * 80)
    print("📋 FIT File Data Structure Summary Table")
    print("=" * 80)
    
    # 1. Data type overview table
    overview_data = []
    for data_type in ['session', 'record', 'lap']:
        overview_data.append({
            'Data Type': data_type.upper(),
            'Record Count': analysis[data_type]['count'],
            'Field Count': len(analysis[data_type]['fields']),
            'Description': {
                'session': 'Exercise summary information (overall statistics for the entire workout)',
                'record': 'Real-time recorded data (detailed measurements per second)',
                'lap': 'Segment recorded data (statistics per kilometer or manual segment)'
            }[data_type]
        })
    
    overview_df = pd.DataFrame(overview_data)
    print("\n📊 Data Type Overview:")
    print(overview_df.to_string(index=False))
    
    # 2. Important field classification table
    important_fields = {
        'session': ['timestamp', 'start_time', 'sport', 'sub_sport', 'total_distance', 
                   'total_timer_time', 'total_calories', 'avg_heart_rate', 'max_heart_rate', 
                   'enhanced_avg_speed'],
        'record': ['timestamp', 'position_lat', 'position_long', 'distance', 'enhanced_speed', 
                  'enhanced_altitude', 'heart_rate', 'cadence', 'vertical_oscillation', 
                  'stance_time'],
        'lap': ['timestamp', 'start_time', 'total_distance', 'total_timer_time', 
               'avg_heart_rate', 'max_heart_rate', 'enhanced_avg_speed']
    }
    
    # 3. 各類型詳細欄位表
    for data_type in ['session', 'record', 'lap']:
        print(f"\n📝 {data_type.upper()} 欄位詳細表:")
        
        field_data = []
        for field_name in analysis[data_type]['fields']:
            field_info = analysis[data_type]['field_details'][field_name]
            
            # 判斷是否為重要欄位
            is_important = field_name in important_fields.get(data_type, [])
            
            row = {
                '欄位名稱': field_name,
                '重要性': '🌟 重要' if is_important else '📋 一般',
                '資料類型': field_info['type'],
                '單位': field_info['units'],
                '範例值': field_info['sample_value']
            }
            
            # Record 類型增加頻率資訊
            if data_type == 'record':
                row['出現頻率'] = field_info.get('frequency', '')
                row['百分比'] = field_info.get('percentage', '')
            
            field_data.append(row)
        
        # 按重要性排序
        field_data.sort(key=lambda x: (x['重要性'] != '🌟 重要', x['欄位名稱']))
        
        field_df = pd.DataFrame(field_data)
        print(field_df.to_string(index=False))
    
    # 4. 統計摘要
    print(f"\n📊 總計統計:")
    print(f"  • 總資料筆數: {sum(analysis[dt]['count'] for dt in ['session', 'record', 'lap'])} 筆")
    print(f"  • Session 欄位: {len(analysis['session']['fields'])} 個")
    print(f"  • Record 欄位: {len(analysis['record']['fields'])} 個")
    print(f"  • Lap 欄位: {len(analysis['lap']['fields'])} 個")
    print(f"  • 總欄位數 (去重): {len(set().union(*[analysis[dt]['fields'] for dt in ['session', 'record', 'lap']]))} 個")


def export_to_csv(analysis, output_dir="./"):
    """匯出分析結果到 CSV 檔案"""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n💾 匯出分析結果到 CSV 檔案...")
    
    # 匯出各個數據類型的欄位詳細資訊
    for data_type in ['session', 'record', 'lap']:
        field_data = []
        for field_name in analysis[data_type]['fields']:
            field_info = analysis[data_type]['field_details'][field_name]
            field_data.append(field_info)
        
        if field_data:
            df = pd.DataFrame(field_data)
            csv_file = output_dir / f"fit_{data_type}_fields.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"  ✅ {data_type.upper()} 欄位: {csv_file}")
    
    # 匯出概覽表
    overview_data = []
    for data_type in ['session', 'record', 'lap']:
        overview_data.append({
            'data_type': data_type,
            'count': analysis[data_type]['count'],
            'field_count': len(analysis[data_type]['fields'])
        })
    
    overview_df = pd.DataFrame(overview_data)
    overview_csv = output_dir / "fit_overview.csv"
    overview_df.to_csv(overview_csv, index=False, encoding='utf-8-sig')
    print(f"  ✅ 概覽表: {overview_csv}")


def main():
    """主函數"""
    
    # FIT 檔案路徑
    fit_file_path = '/home/aiuser/codetrekking/storage/garmin/example@gmail.com/activities/19329066809_ACTIVITY.fit'
    
    # 檢查檔案是否存在
    if not Path(fit_file_path).exists():
        print(f"❌ 找不到 FIT 檔案: {fit_file_path}")
        return
    
    try:
        # 分析 FIT 檔案
        analysis = analyze_fit_file(fit_file_path)
        
        # 創建摘要表格
        create_summary_tables(analysis)
        
        # 匯出 CSV
        export_to_csv(analysis, "./fit_analysis_output")
        
        print(f"\n✅ 分析完成！")
        
    except Exception as e:
        print(f"❌ 分析過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()