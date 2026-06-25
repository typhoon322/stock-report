"""
rotation/rti_ml.py — RTI 机器学习模型

Baseline: Logistic Regression
输出: RTI_v2 = P(板块在未来3天成为主线)

混合模式: 0.8 * rule_score + 0.2 * ml_score (v1测试期)
"""
import pickle, json, os
from typing import List, Dict, Optional, Tuple
import numpy as np

from .audit_builder import AuditBundle, bundles_to_arrays

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "rotation", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, "rti_model.pkl")
WEIGHTS_PATH = os.path.join(MODEL_DIR, "rti_weights.json")


class RTIMLModel:
    """RTI 机器学习模型包装器"""
    
    def __init__(self):
        self.model = None
        self.coef_ = None
        self.intercept_ = None
        self.feature_names = AuditBundle.feature_names()
        self.trained = False
        self.training_date = None
    
    def train(self, bundles: List[AuditBundle]):
        """训练模型"""
        if len(bundles) < 50:
            print(f"  ⚠ 训练样本不足: {len(bundles)}, 需要至少50个")
            return False
        
        X, y = bundles_to_arrays(bundles)
        
        # 检查正负样本平衡
        pos = int(sum(y))
        neg = len(y) - pos
        print(f"  样本: {len(y)} (正{pos}, 负{neg})")
        
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        
        # 标准化
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # 逻辑回归
        self.model = LogisticRegression(
            class_weight='balanced',
            max_iter=1000,
            random_state=42,
        )
        self.model.fit(X_scaled, y)
        
        self.coef_ = self.model.coef_[0].tolist()
        self.intercept_ = float(self.model.intercept_[0])
        self.trained = True
        self.training_date = str(np.datetime64('today'))
        
        # 保存权重解释
        weights = {
            name: round(coef, 4)
            for name, coef in zip(self.feature_names, self.coef_)
        }
        weights["intercept"] = self.intercept_
        weights["training_date"] = self.training_date
        weights["n_samples"] = len(y)
        weights["positive_rate"] = round(pos / max(len(y), 1), 3)
        
        with open(WEIGHTS_PATH, 'w') as f:
            json.dump(weights, f, indent=2)
        
        print(f"  ✅ 模型训练完成")
        print(f"  权重: {weights}")
        return True
    
    def predict_proba(self, features: List[float]) -> float:
        """预测概率 RTI_v2 = P(成为主线)"""
        if not self.trained or self.model is None:
            return 0.0
        
        X = np.array([features])
        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)
        return float(proba[0, 1])  # 正类概率
    
    def predict_batch(self, bundles: List[AuditBundle]) -> List[float]:
        """批量预测"""
        if not self.trained or self.model is None:
            return [0.0] * len(bundles)
        
        X = np.array([b.to_feature_vector() for b in bundles])
        X_scaled = self.scaler.transform(X)
        probas = self.model.predict_proba(X_scaled)
        return probas[:, 1].tolist()
    
    def save(self):
        """保存模型"""
        if not self.trained:
            return
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'coef_': self.coef_,
                'intercept_': self.intercept_,
                'feature_names': self.feature_names,
                'training_date': self.training_date,
            }, f)
        print(f"  ✅ 模型保存: {MODEL_PATH}")
    
    def load(self) -> bool:
        """加载模型"""
        if not os.path.exists(MODEL_PATH):
            return False
        try:
            with open(MODEL_PATH, 'rb') as f:
                data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.coef_ = data['coef_']
            self.intercept_ = data['intercept_']
            self.feature_names = data['feature_names']
            self.training_date = data.get('training_date', 'unknown')
            self.trained = True
            return True
        except Exception as e:
            print(f"  ⚠ 模型加载失败: {e}")
            return False
    
    def get_weights_report(self) -> Dict:
        """权重报告: 哪些特征最重要"""
        if not self.trained:
            return {"status": "not_trained"}
        
        pairs = sorted(
            zip(self.feature_names, self.coef_),
            key=lambda x: abs(x[1]), reverse=True
        )
        return {
            "training_date": self.training_date,
            "top_features": [{"feature": f, "weight": w} for f, w in pairs],
            "intercept": self.intercept_,
        }


def compute_rti_hybrid(
    features: List[float],
    model: RTIMLModel,
    rule_score: float,
    ml_weight: float = 0.2,  # 初始ML权重20%
) -> Tuple[float, float, float]:
    """
    混合模式 RTI
    
    Returns: (hybrid_score, rule_score, ml_score)
    """
    ml_score = model.predict_proba(features) if model.trained else 0.5
    hybrid = (1 - ml_weight) * rule_score + ml_weight * ml_score
    return hybrid, rule_score, ml_score
