"""
Ensemble ML Predictor - Sistema de Prediccin con Mltiples Modelos
Combina Random Forest, XGBoost, y otros modelos para mayor precisin
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import warnings
warnings.filterwarnings('ignore')


@dataclass
class ModelPrediction:
    """Prediccin de un modelo individual"""
    model_name: str
    prediction: int  # 0=PUT, 1=CALL
    probability: float  # Probabilidad de la prediccin
    confidence: float  # Confianza del modelo


@dataclass
class EnsemblePrediction:
    """Prediccin consolidada del ensemble"""
    final_prediction: int  # 0=PUT, 1=CALL
    confidence: float  # Confianza consolidada 0-1
    model_predictions: List[ModelPrediction]
    agreement_score: float  # Cuntos modelos coinciden (0-1)
    recommended_action: str  # "CALL", "PUT", "WAIT"
    expected_accuracy: float  # Accuracy esperada basada en validacin


class EnsembleMLPredictor:
    """
    Ensemble ML Predictor - Combina mltiples modelos para mayor precisin

    Modelos incluidos:
    - Random Forest (robusto, menos overfitting)
    - Gradient Boosting (alta precisin)
    - XGBoost (si disponible, state-of-the-art)
    - Logistic Regression (baseline lineal)
    - SVM (bueno para fronteras no lineales)
    - MLP Classifier (red neuronal superficial)

    El ensemble usa voting suave (promedio de probabilidades) para mayor estabilidad
    """

    def __init__(
        self,
        use_xgboost: bool = False,
        n_estimators: int = 100,
        max_depth: int = 10
    ):
        self.use_xgboost = use_xgboost
        self.n_estimators = n_estimators
        self.max_depth = max_depth

        # Modelos
        self.models: Dict[str, object] = {}
        self.ensemble: Optional[VotingClassifier] = None
        self.scaler: Optional[StandardScaler] = None

        # Mtricas de validacin
        self.model_metrics: Dict[str, Dict] = {}
        self.feature_importance: Dict[str, float] = {}

        # Estado
        self.is_trained = False
        self.last_training_date: Optional[datetime] = None
        self.training_samples: int = 0

        # Intentar importar XGBoost
        self.xgboost_available = False
        if use_xgboost:
            try:
                import xgboost as xgb
                self.xgboost_available = True
            except ImportError:
                print(" XGBoost no disponible, usando solo modelos sklearn")

        self._initialize_models()

    def _initialize_models(self):
        """Inicializar todos los modelos"""
        # Random Forest
        self.models['random_forest'] = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )

        # Gradient Boosting
        self.models['gradient_boosting'] = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=5,
            learning_rate=0.1,
            min_samples_split=5,
            random_state=42
        )

        # Logistic Regression
        self.models['logistic_regression'] = LogisticRegression(
            C=1.0,
            class_weight='balanced',
            max_iter=1000,
            random_state=42
        )

        # SVM
        self.models['svm'] = SVC(
            kernel='rbf',
            C=1.0,
            probability=True,
            class_weight='balanced',
            random_state=42
        )

        # MLP Classifier
        self.models['mlp'] = MLPClassifier(
            hidden_layer_sizes=(64, 32),
            activation='relu',
            solver='adam',
            alpha=0.001,
            max_iter=500,
            random_state=42,
            early_stopping=True
        )

        # XGBoost (si disponible)
        if self.xgboost_available:
            import xgboost as xgb
            self.models['xgboost'] = xgb.XGBClassifier(
                n_estimators=50,
                max_depth=6,
                learning_rate=0.1,
                objective='binary:logistic',
                eval_metric='logloss',
                random_state=42,
                use_label_encoder=False
            )

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preparar features para el modelo

        Args:
            df: DataFrame con datos de mercado

        Returns:
            DataFrame con features listas para prediccin
        """
        feature_df = df.copy()

        # Features tcnicos bsicos
        feature_df = self._add_technical_features(feature_df)

        # Features de momentum
        feature_df = self._add_momentum_features(feature_df)

        # Features de volatilidad
        feature_df = self._add_volatility_features(feature_df)

        # Features de volumen (si disponible)
        if 'volume' in feature_df.columns:
            feature_df = self._add_volume_features(feature_df)

        # Seleccionar solo columnas numricas
        numeric_cols = feature_df.select_dtypes(include=[np.number]).columns
        feature_df = feature_df[numeric_cols]

        # Eliminar NaN/Inf
        feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
        feature_df = feature_df.fillna(method='ffill').fillna(0)

        return feature_df

    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar features tcnicos"""
        # EMAs
        df['ema_9'] = df['close'].ewm(span=9).mean()
        df['ema_21'] = df['close'].ewm(span=21).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()

        # Diferencias de EMAs
        df['ema_9_21_diff'] = df['ema_9'] - df['ema_21']
        df['ema_9_50_diff'] = df['ema_9'] - df['ema_50']

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False)
        exp2 = df['close'].ewm(span=26, adjust=False)
        df['macd'] = exp1.mean() - exp2.mean()
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        return df

    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar features de momentum"""
        # Retornos
        df['return_1'] = df['close'].pct_change(1)
        df['return_5'] = df['close'].pct_change(5)
        df['return_10'] = df['close'].pct_change(10)
        df['return_20'] = df['close'].pct_change(20)

        # Momentum simple
        df['momentum_5'] = df['close'] - df['close'].shift(5)
        df['momentum_10'] = df['close'] - df['close'].shift(10)

        # Tasa de cambio
        df['roc_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
        df['roc_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100

        return df

    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar features de volatilidad"""
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(14).mean()
        df['atr_pct'] = (df['atr'] / df['close']) * 100

        # Volatilidad histrica
        df['volatility_10'] = df['return_1'].rolling(10).std()
        df['volatility_20'] = df['return_1'].rolling(20).std()

        # Rango de velas
        df['candle_range'] = (df['high'] - df['low']) / df['close']
        df['candle_range_avg'] = df['candle_range'].rolling(10).mean()

        return df

    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar features de volumen"""
        # Volumen relativo
        df['volume_ma_20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_20']

        # OBV (On Balance Volume)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

        return df

    def train(
        self,
        df: pd.DataFrame,
        target_column: str = 'next_candle_direction',
        test_size: float = 0.2,
        cross_validation_folds: int = 5
    ):
        """
        Entrenar todos los modelos

        Args:
            df: DataFrame con datos histricos
            target_column: Nombre de la columna objetivo (1=CALL, 0=PUT)
            test_size: Proporcin para test
            cross_validation_folds: Folds para cross-validation
        """
        print(" Entrenando Ensemble ML Predictor...")

        # Preparar features
        feature_df = self.prepare_features(df)

        # Eliminar filas con NaN
        feature_df = feature_df.dropna()

        if len(feature_df) < 100:
            print(" Datos insuficientes para entrenar (mnimo 100 muestras)")
            return

        # Separar features y target
        feature_cols = [c for c in feature_df.columns if c != target_column]
        X = feature_df[feature_cols]
        y = feature_df[target_column]

        # Split train/test
        split_idx = int(len(X) * (1 - test_size))
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        print(f"  Muestras train: {len(X_train)}, test: {len(X_test)}")

        # Escalar features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.training_samples = len(X_train)

        # Entrenar cada modelo individualmente
        self.model_metrics = {}

        for name, model in self.models.items():
            print(f"  Entrenando {name}...")

            try:
                model.fit(X_train_scaled, y_train)

                # Predicciones en test
                y_pred = model.predict(X_test_scaled)
                y_proba = model.predict_proba(X_test_scaled)[:, 1] if hasattr(model, 'predict_proba') else y_pred

                # Mtricas
                accuracy = accuracy_score(y_test, y_pred)
                precision = precision_score(y_test, y_pred, zero_division=0)
                recall = recall_score(y_test, y_pred, zero_division=0)
                f1 = f1_score(y_test, y_pred, zero_division=0)

                # Cross-validation
                cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=cross_validation_folds, scoring='accuracy')

                self.model_metrics[name] = {
                    'accuracy': accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1': f1,
                    'cv_mean': cv_scores.mean(),
                    'cv_std': cv_scores.std(),
                }

                print(f"     {name}: Accuracy={accuracy*100:.1f}%, CV={cv_scores.mean()*100:.1f}%")

            except Exception as e:
                print(f"     Error entrenando {name}: {e}")
                self.model_metrics[name] = {
                    'accuracy': 0.5,
                    'error': str(e)
                }

        # Crear ensemble con voting suave
        estimators = [
            (name, model) for name, model in self.models.items()
            if name in self.model_metrics and 'error' not in self.model_metrics.get(name, {})
        ]

        if len(estimators) >= 2:
            self.ensemble = VotingClassifier(
                estimators=estimators,
                voting='soft',
                weights=[self.model_metrics[n]['cv_mean'] for n, _ in estimators]
            )
            self.ensemble.fit(X_train_scaled, y_train)

            # Mtricas del ensemble
            ensemble_pred = self.ensemble.predict(X_test_scaled)
            self.model_metrics['ensemble'] = {
                'accuracy': accuracy_score(y_test, ensemble_pred),
                'cv_mean': cross_val_score(self.ensemble, X_train_scaled, y_train, cv=cross_validation_folds).mean(),
            }
            print(f"   Ensemble: Accuracy={self.model_metrics['ensemble']['accuracy']*100:.1f}%")

        # Feature importance (promedio de Random Forest y Gradient Boosting)
        self._calculate_feature_importance(feature_cols)

        self.is_trained = True
        self.last_training_date = datetime.now()

        print(f" Entrenamiento completado ({len(self.models)} modelos)")

    def _calculate_feature_importance(self, feature_cols: List[str]):
        """Calcular importancia de features"""
        importance_dict = {}

        # Random Forest importance
        if 'random_forest' in self.models and hasattr(self.models['random_forest'], 'feature_importances_'):
            rf_importance = self.models['random_forest'].feature_importances_
            for i, col in enumerate(feature_cols):
                importance_dict[col] = importance_dict.get(col, 0) + rf_importance[i] * 0.5

        # Gradient Boosting importance
        if 'gradient_boosting' in self.models and hasattr(self.models['gradient_boosting'], 'feature_importances_'):
            gb_importance = self.models['gradient_boosting'].feature_importances_
            for i, col in enumerate(feature_cols):
                importance_dict[col] = importance_dict.get(col, 0) + gb_importance[i] * 0.5

        # Normalizar
        total = sum(importance_dict.values())
        if total > 0:
            self.feature_importance = {k: v/total for k, v in importance_dict.items()}

    def predict(self, df: pd.DataFrame) -> EnsemblePrediction:
        """
        Predecir direccin siguiente usando ensemble

        Args:
            df: DataFrame con datos recientes

        Returns:
            EnsemblePrediction con prediccin consolidada
        """
        if not self.is_trained:
            raise Exception("Modelo no entrenado. Llamar a train() primero.")

        if self.scaler is None:
            raise Exception("Scaler no inicializado")

        # Preparar features
        feature_df = self.prepare_features(df)
        feature_df = feature_df.iloc[-1:].dropna()  # ltima fila

        if len(feature_df) == 0:
            raise Exception("No se pudo preparar features vlidas")

        feature_cols = [c for c in feature_df.columns]
        X = feature_df[feature_cols]
        X_scaled = self.scaler.transform(X)

        # Predicciones individuales
        model_predictions: List[ModelPrediction] = []
        call_votes = 0
        put_votes = 0
        weighted_call_prob = 0
        weighted_put_prob = 0
        total_weight = 0

        for name, model in self.models.items():
            try:
                pred = model.predict(X_scaled)[0]
                proba = model.predict_proba(X_scaled)[0] if hasattr(model, 'predict_proba') else [0.5, 0.5]

                # Peso basado en CV accuracy
                weight = self.model_metrics.get(name, {}).get('cv_mean', 0.5)

                if pred == 1:  # CALL
                    call_votes += weight
                    weighted_call_prob += proba[1] * weight
                else:  # PUT
                    put_votes += weight
                    weighted_put_prob += proba[0] * weight

                total_weight += weight

                model_predictions.append(ModelPrediction(
                    model_name=name,
                    prediction=int(pred),
                    probability=float(max(proba)),
                    confidence=float(max(proba))
                ))

            except Exception as e:
                print(f" Error en prediccin {name}: {e}")

        # Prediccin del ensemble (si disponible)
        if self.ensemble:
            ensemble_pred = self.ensemble.predict(X_scaled)[0]
            ensemble_proba = self.ensemble.predict_proba(X_scaled)[0]
            final_prediction = int(ensemble_pred)
            confidence = float(max(ensemble_proba))
        else:
            # Votacin ponderada
            if call_votes > put_votes:
                final_prediction = 1
                confidence = weighted_call_prob / total_weight if total_weight > 0 else 0.5
            else:
                final_prediction = 0
                confidence = weighted_put_prob / total_weight if total_weight > 0 else 0.5

        # Calcular agreement score
        call_count = sum(1 for p in model_predictions if p.prediction == 1)
        put_count = sum(1 for p in model_predictions if p.prediction == 0)
        total_models = len(model_predictions)
        agreement_score = max(call_count, put_count) / total_models if total_models > 0 else 0

        # Determinar accin recomendada
        if confidence >= 0.6 and agreement_score >= 0.6:
            recommended_action = "CALL" if final_prediction == 1 else "PUT"
        elif confidence >= 0.55:
            recommended_action = "CALL" if final_prediction == 1 else "PUT"
        else:
            recommended_action = "WAIT"

        # Accuracy esperada (basada en mtricas de validacin)
        expected_accuracy = self.model_metrics.get('ensemble', {}).get('accuracy', 0.5)
        if not expected_accuracy:
            expected_accuracy = np.mean([
                m.get('cv_mean', 0.5) for m in self.model_metrics.values()
                if 'error' not in m
            ])

        return EnsemblePrediction(
            final_prediction=final_prediction,
            confidence=confidence,
            model_predictions=model_predictions,
            agreement_score=agreement_score,
            recommended_action=recommended_action,
            expected_accuracy=expected_accuracy
        )

    def get_model_report(self) -> str:
        """Generar reporte de modelos"""
        report = []
        report.append("=" * 70)
        report.append("REPORTE DE ENSEMBLE ML PREDICTOR")
        report.append("=" * 70)
        report.append(f"Estado: {' Entrenado' if self.is_trained else ' No entrenado'}")
        report.append(f"ltimo entrenamiento: {self.last_training_date}")
        report.append(f"Muestras entrenamiento: {self.training_samples}")
        report.append(f"Modelos disponibles: {len(self.models)}")
        report.append("")
        report.append("MTRICAS POR MODELO:")
        report.append("-" * 50)

        for name, metrics in self.model_metrics.items():
            if 'error' in metrics:
                report.append(f"  {name}: ERROR - {metrics['error']}")
            else:
                report.append(f"  {name}:")
                report.append(f"    Accuracy: {metrics.get('accuracy', 0)*100:.1f}%")
                report.append(f"    CV Mean: {metrics.get('cv_mean', 0)*100:.1f}% (+/- {metrics.get('cv_std', 0)*3:.1f}%)")

        report.append("")
        report.append("TOP 10 FEATURES MS IMPORTANTES:")
        report.append("-" * 50)

        sorted_importance = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        for feature, importance in sorted_importance:
            bar = "" * int(importance * 50)
            report.append(f"  {feature:30s} {importance*100:5.1f}% {bar}")

        report.append("=" * 70)

        return "\n".join(report)

    def save(self, filepath: str):
        """Guardar modelo a disco"""
        if not self.is_trained:
            print(" No hay modelo entrenado para guardar")
            return

        model_data = {
            'models': self.models,
            'ensemble': self.ensemble,
            'scaler': self.scaler,
            'model_metrics': self.model_metrics,
            'feature_importance': self.feature_importance,
            'is_trained': self.is_trained,
            'last_training_date': self.last_training_date,
            'training_samples': self.training_samples,
        }

        joblib.dump(model_data, filepath)
        print(f" Modelo guardado en {filepath}")

    def load(self, filepath: str) -> bool:
        """Cargar modelo desde disco"""
        if not os.path.exists(filepath):
            print(f" Archivo no encontrado: {filepath}")
            return False

        try:
            model_data = joblib.load(filepath)

            self.models = model_data.get('models', {})
            self.ensemble = model_data.get('ensemble')
            self.scaler = model_data.get('scaler')
            self.model_metrics = model_data.get('model_metrics', {})
            self.feature_importance = model_data.get('feature_importance', {})
            self.is_trained = model_data.get('is_trained', False)
            self.last_training_date = model_data.get('last_training_date')
            self.training_samples = model_data.get('training_samples', 0)

            print(f" Modelo cargado desde {filepath}")
            return True

        except Exception as e:
            print(f" Error cargando modelo: {e}")
            return False


# Singleton
_predictor: Optional[EnsembleMLPredictor] = None


def get_ensemble_predictor() -> EnsembleMLPredictor:
    """Obtener instancia singleton"""
    global _predictor
    if _predictor is None:
        _predictor = EnsembleMLPredictor()
    return _predictor
