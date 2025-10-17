#!/usr/bin/env python3

import time
import datetime
import argparse
import signal
import numpy as np
from collections import deque
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
from lib.xAppBase import xAppBase


class MLResourceOptimizerXapp(xAppBase):
    def __init__(self, http_server_port, rmr_port):
        super(MLResourceOptimizerXapp, self).__init__('', http_server_port, rmr_port)
        
        # Data storage for time series analysis
        self.ue_metrics_history = {}  # Store historical metrics for each UE
        self.cell_metrics_history = {}  # Store historical metrics for each cell
        self.max_history_length = 100  # Keep last 100 data points
        
        # ML models
        self.scaler = StandardScaler()
        self.prb_predictor = RandomForestRegressor(n_estimators=50, random_state=42)
        self.handover_predictor = RandomForestClassifier(n_estimators=50, random_state=42)
        
        # Model state
        self.model_trained = False
        self.training_data_X = []
        self.training_data_y_prb = []
        self.training_data_y_ho = []
        
        # Control parameters
        self.min_prb_ratio = 1
        self.max_prb_ratio_low = 10
        self.max_prb_ratio_high = 100
        self.prb_threshold_mb = 20
        
        # Prediction window (in seconds)
        self.prediction_window = 30

    def collect_training_data(self, ue_id, metrics_data, prb_setting, ho_event=0):
        """Collect data for training ML models"""
        features = []
        
        # Extract features from metrics
        if ue_id in self.ue_metrics_history:
            history = self.ue_metrics_history[ue_id]
            
            # Current metrics
            current_dl = metrics_data.get("DRB.UEThpDl", [0])[0] if "DRB.UEThpDl" in metrics_data else 0
            current_ul = metrics_data.get("DRB.UEThpUl", [0])[0] if "DRB.UEThpUl" in metrics_data else 0
            
            # Historical averages
            avg_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-10:]]) if len(history) > 0 else 0
            avg_ul = np.mean([m.get("DRB.UEThpUl", [0])[0] for m in history[-10:]]) if len(history) > 0 else 0
            
            # Trend features
            if len(history) > 5:
                recent_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-3:]])
                older_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-6:-3]])
                dl_trend = recent_dl - older_dl
            else:
                dl_trend = 0
                
            features = [current_dl, current_ul, avg_dl, avg_ul, dl_trend, len(history)]
            
            # Store training data
            self.training_data_X.append(features)
            self.training_data_y_prb.append(prb_setting)
            self.training_data_y_ho.append(ho_event)
            
            # Keep training data size manageable
            if len(self.training_data_X) > 1000:
                self.training_data_X = self.training_data_X[-500:]
                self.training_data_y_prb = self.training_data_y_prb[-500:]
                self.training_data_y_ho = self.training_data_y_ho[-500:]

    def train_models(self):
        """Train ML models when sufficient data is available"""
        if len(self.training_data_X) < 20:
            return False
            
        X = np.array(self.training_data_X)
        y_prb = np.array(self.training_data_y_prb)
        y_ho = np.array(self.training_data_y_ho)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train models
        self.prb_predictor.fit(X_scaled, y_prb)
        # For classifier, we need at least 2 classes
        if len(np.unique(y_ho)) > 1:
            self.handover_predictor.fit(X_scaled, y_ho)
        
        self.model_trained = True
        print(f"ML models trained with {len(self.training_data_X)} samples")
        return True

    def predict_prb_setting(self, ue_id, metrics_data):
        """Predict optimal PRB setting using ML model"""
        if not self.model_trained:
            return self.max_prb_ratio_high  # Default to high if no model
            
        # Extract features
        if ue_id in self.ue_metrics_history and len(self.ue_metrics_history[ue_id]) > 0:
            history = self.ue_metrics_history[ue_id]
            
            current_dl = metrics_data.get("DRB.UEThpDl", [0])[0] if "DRB.UEThpDl" in metrics_data else 0
            current_ul = metrics_data.get("DRB.UEThpUl", [0])[0] if "DRB.UEThpUl" in metrics_data else 0
            
            avg_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-10:]]) if len(history) > 0 else 0
            avg_ul = np.mean([m.get("DRB.UEThpUl", [0])[0] for m in history[-10:]]) if len(history) > 0 else 0
            
            if len(history) > 5:
                recent_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-3:]])
                older_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-6:-3]])
                dl_trend = recent_dl - older_dl
            else:
                dl_trend = 0
                
            features = np.array([[current_dl, current_ul, avg_dl, avg_ul, dl_trend, len(history)]])
            features_scaled = self.scaler.transform(features)
            
            predicted_prb = self.prb_predictor.predict(features_scaled)[0]
            
            # Convert continuous prediction to discrete settings
            if predicted_prb > (self.max_prb_ratio_high + self.max_prb_ratio_low) / 2:
                return self.max_prb_ratio_high
            else:
                return self.max_prb_ratio_low
        else:
            return self.max_prb_ratio_high

    def predict_handover_need(self, ue_id, metrics_data):
        """Predict if handover is needed using ML model"""
        if not self.model_trained:
            return False
            
        # Extract features (similar to PRB prediction)
        if ue_id in self.ue_metrics_history and len(self.ue_metrics_history[ue_id]) > 0:
            history = self.ue_metrics_history[ue_id]
            
            current_dl = metrics_data.get("DRB.UEThpDl", [0])[0] if "DRB.UEThpDl" in metrics_data else 0
            current_ul = metrics_data.get("DRB.UEThpUl", [0])[0] if "DRB.UEThpUl" in metrics_data else 0
            
            avg_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-10:]]) if len(history) > 0 else 0
            avg_ul = np.mean([m.get("DRB.UEThpUl", [0])[0] for m in history[-10:]]) if len(history) > 0 else 0
            
            if len(history) > 5:
                recent_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-3:]])
                older_dl = np.mean([m.get("DRB.UEThpDl", [0])[0] for m in history[-6:-3]])
                dl_trend = recent_dl - older_dl
            else:
                dl_trend = 0
                
            features = np.array([[current_dl, current_ul, avg_dl, avg_ul, dl_trend, len(history)]])
            features_scaled = self.scaler.transform(features)
            
            # Check if we have a trained classifier with classes
            if hasattr(self.handover_predictor, 'classes_') and len(self.handover_predictor.classes_) > 1:
                ho_probability = self.handover_predictor.predict_proba(features_scaled)[0][1]
                return ho_probability > 0.7  # 70% threshold
            else:
                return False
        else:
            return False

    def update_metrics_history(self, ue_id, metrics_data):
        """Update historical metrics for a UE"""
        if ue_id not in self.ue_metrics_history:
            self.ue_metrics_history[ue_id] = deque(maxlen=self.max_history_length)
        
        self.ue_metrics_history[ue_id].append(metrics_data)
        
        # Periodically retrain models
        if len(self.training_data_X) % 50 == 0 and len(self.training_data_X) > 20:
            self.train_models()

    def my_subscription_callback(self, e2_agent_id, subscription_id, indication_hdr, indication_msg, kpm_report_style, ue_id):
        indication_hdr = self.e2sm_kpm.extract_hdr_info(indication_hdr)
        meas_data = self.e2sm_kpm.extract_meas_data(indication_msg)

        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] ML Resource Optimizer - Data Monitoring:")
        print("  E2SM_KPM RIC Indication Content:")
        print("  -CollectionStartTime: ", indication_hdr['colletStartTime'])

        # Process UE-level metrics
        if "ueMeasData" in meas_data:
            for ue_id, ue_meas_data in meas_data["ueMeasData"].items():
                print(f"  --UE_id: {ue_id}")
                
                # Extract and display metrics
                metrics_summary = {}
                for metric_name, values in ue_meas_data["measData"].items():
                    # Extract actual values from the tuple format (type, value)
                    actual_values = [val[1] if isinstance(val, tuple) else val for val in values]
                    value = sum(actual_values) if actual_values else 0
                    metrics_summary[metric_name] = actual_values
                    print(f"  ---Metric: {metric_name}, Value: {value}")

                # Update history
                self.update_metrics_history(ue_id, metrics_summary)
                
                # Predict optimal PRB setting
                predicted_prb = self.predict_prb_setting(ue_id, metrics_summary)
                print(f"  ---Predicted PRB Setting: {predicted_prb}")
                
                # Send control command
                current_time = datetime.datetime.now()
                print(f"  [{current_time.strftime('%H:%M:%S')}] Send RIC Control Request to E2 node ID: {e2_agent_id} for UE ID: {ue_id}, PRB_min: {self.min_prb_ratio}, PRB_max: {predicted_prb}")
                self.e2sm_rc.control_slice_level_prb_quota(e2_agent_id, ue_id, 
                                                           min_prb_ratio=self.min_prb_ratio, 
                                                           max_prb_ratio=predicted_prb, 
                                                           dedicated_prb_ratio=100, 
                                                           ack_request=1)
                
                # Collect training data
                # In a real implementation, we would know the actual outcome
                actual_prb = predicted_prb  # Placeholder
                self.collect_training_data(ue_id, metrics_summary, actual_prb)

        print("------------------------------------------------------------------")

    @xAppBase.start_function
    def start(self, e2_node_id, kpm_report_style, ue_ids, metric_names):
        report_period = 2000  # 2 seconds for more stable predictions
        granul_period = 2000

        subscription_callback = lambda agent, sub, hdr, msg: self.my_subscription_callback(agent, sub, hdr, msg, kpm_report_style, None)

        # Matching conditions for UEs
        matchingUeConds = [{'testCondInfo': {'testType': ('ul-rSRP', 'true'), 'testExpr': 'lessthan', 'testValue': ('valueInt', 1000)}}]
        
        print(f"Subscribe to E2 node ID: {e2_node_id}, RAN func: e2sm_kpm, Report Style: {kpm_report_style}, metrics: {metric_names}")
        self.e2sm_kpm.subscribe_report_service_style_4(e2_node_id, report_period, matchingUeConds, metric_names, granul_period, subscription_callback)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ML Resource Optimizer xApp')
    parser.add_argument("--http_server_port", type=int, default=8095, help="HTTP server listen port")
    parser.add_argument("--rmr_port", type=int, default=4565, help="RMR port")
    parser.add_argument("--e2_node_id", type=str, default='gnbd_001_001_00019b_0', help="E2 Node ID")
    parser.add_argument("--ran_func_id", type=int, default=2, help="RAN function ID")
    parser.add_argument("--kpm_report_style", type=int, default=4, help="KPM Report Style ID")
    parser.add_argument("--ue_ids", type=str, default='0', help="UE ID")
    parser.add_argument("--metrics", type=str, default='DRB.UEThpDl,DRB.UEThpUl', help="Metrics name as comma-separated string")

    args = parser.parse_args()
    e2_node_id = args.e2_node_id
    ran_func_id = args.ran_func_id
    ue_ids = list(map(int, args.ue_ids.split(",")))
    kpm_report_style = args.kpm_report_style
    metrics = args.metrics.split(",")

    # Create xApp
    myXapp = MLResourceOptimizerXapp(args.http_server_port, args.rmr_port)
    myXapp.e2sm_kpm.set_ran_func_id(ran_func_id)

    # Connect exit signals
    signal.signal(signal.SIGQUIT, myXapp.signal_handler)
    signal.signal(signal.SIGTERM, myXapp.signal_handler)
    signal.signal(signal.SIGINT, myXapp.signal_handler)

    # Start xApp
    myXapp.start(e2_node_id, kpm_report_style, ue_ids, metrics)