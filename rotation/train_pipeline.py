"""
rotation/train_pipeline.py — 训练管道

从历史数据 → AuditBundle训练集 → 训练LogisticRegression → 保存模型
"""
import os, sys, json
from datetime import datetime

from .history import build_history
from .audit_builder import build_dataset_from_history, AuditBundle
from .rti_ml import RTIMLModel


def build_training_set(days: int = 60) -> list:
    """构建训练数据集"""
    print(f"📦 构建训练数据 (最近{days}天)...")
    history = build_history(days=days)
    bundles = build_dataset_from_history(history, lookback_days=3)
    return bundles


def train_pipeline(days: int = 60):
    """
    完整训练管道
    
    1. 采集历史数据
    2. 构建训练集
    3. 训练LogisticRegression
    4. 保存模型
    5. 输出权重报告
    """
    print("=" * 60)
    print("🧠 RTI ML 训练管道")
    print("=" * 60)
    
    # Step 1+2: 构建训练集
    bundles = build_training_set(days)
    if not bundles:
        print("❌ 训练数据不足，无法训练")
        return None
    
    # Step 3: 训练
    model = RTIMLModel()
    success = model.train(bundles)
    if not success:
        return None
    
    # Step 4: 保存
    model.save()
    
    # Step 5: 权重报告
    report = model.get_weights_report()
    print("\n📊 特征重要性 (LogisticRegression coef_):")
    for item in report.get("top_features", []):
        direction = "📈" if item["weight"] > 0 else "📉"
        print(f"  {direction} {item['feature']:20s}: {item['weight']:+.4f}")
    print(f"  📍 intercept: {report.get('intercept', 0):+.4f}")
    
    return model


def quick_train():
    """快速训练 (从现有缓存的60天数据)"""
    return train_pipeline(days=60)
