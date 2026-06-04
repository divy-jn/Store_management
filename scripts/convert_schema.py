import json
import uuid
import sys
from pathlib import Path

def convert_events(input_path: str, output_path: str):
    with open(input_path, 'r') as f_in, open(output_path, 'w') as f_out:
        for line in f_in:
            if not line.strip():
                continue
            event = json.loads(line)
            
            e_type = event.get("event_type", "").upper()
            vis_id = event.get("visitor_id", "").replace("VIS_", "")
            try:
                track_id = int(vis_id)
            except:
                track_id = hash(vis_id) % 10000
                
            out_event = {}
            
            if e_type == "ENTRY" or e_type == "EXIT":
                out_event = {
                    "event_type": e_type.lower(),
                    "id_token": event.get("visitor_id"),
                    "store_code": f"store_{event.get('store_id', '').replace('ST', '')}",
                    "camera_id": event.get("camera_id"),
                    "event_timestamp": event.get("timestamp"),
                    "is_staff": event.get("is_staff", False),
                    "gender_pred": "U",
                    "age_pred": 30,
                    "age_bucket": "25-34",
                    "is_face_hidden": False,
                    "group_id": None,
                    "group_size": None
                }
            elif e_type == "ZONE_ENTER" or e_type == "ZONE_EXIT":
                out_event = {
                    "event_type": "zone_entered" if e_type == "ZONE_ENTER" else "zone_exited",
                    "track_id": track_id,
                    "store_id": event.get("store_id"),
                    "camera_id": event.get("camera_id"),
                    "zone_id": event.get("zone_id") or "UNKNOWN",
                    "zone_name": event.get("zone_id") or "UNKNOWN",
                    "zone_type": "SHELF",
                    "is_revenue_zone": "Yes",
                    "event_time": event.get("timestamp"),
                    "zone_hotspot_x": 0.0,
                    "zone_hotspot_y": 0.0,
                    "gender": "U",
                    "age": 30,
                    "age_bucket": "25-34"
                }
            elif "QUEUE" in e_type:
                abandoned = "ABANDON" in e_type
                out_event = {
                    "queue_event_id": event.get("event_id"),
                    "event_type": "queue_abandoned" if abandoned else "queue_completed",
                    "track_id": track_id,
                    "store_id": event.get("store_id"),
                    "camera_id": event.get("camera_id"),
                    "zone_id": event.get("zone_id") or "BILLING",
                    "zone_name": "Billing Queue",
                    "zone_type": "BILLING",
                    "is_revenue_zone": "Yes",
                    "queue_join_ts": event.get("timestamp"),
                    "queue_served_ts": None if abandoned else event.get("timestamp"),
                    "queue_exit_ts": event.get("timestamp"),
                    "wait_seconds": 0,
                    "queue_position_at_join": 1,
                    "abandoned": abandoned,
                    "zone_hotspot_x": 0.0,
                    "zone_hotspot_y": 0.0,
                    "gender": "U",
                    "age": 30,
                    "age_bucket": "25-34"
                }
            else:
                continue
                
            f_out.write(json.dumps(out_event) + "\n")

if __name__ == "__main__":
    import glob
    import os
    # find latest jsonl in output/events
    files = glob.glob("output/events/*.jsonl")
    if not files:
        print("No jsonl files found in output/events")
        sys.exit(1)
    
    latest_file = max(files, key=os.path.getctime)
    convert_events(latest_file, "events.jsonl")
    print(f"Successfully converted {latest_file} to events.jsonl")
