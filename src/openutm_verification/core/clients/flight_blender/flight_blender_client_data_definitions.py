from pydantic import BaseModel


class HeartbeatRateDetail(BaseModel):
    measured_rate_hz: float
    target_rate_hz: float
    session_id: str
    window_start: str
    window_end: str
    total_heartbeats_in_window: int


class HeartbeatDeliveryProbabilityDetail(BaseModel):
    probability: float
    delivered_on_time: int
    total_expected: int
    session_id: str
    window_start: str
    window_end: str


class TrackUpdateProbabilityDetail(BaseModel):
    probability: float
    ticks_with_active_tracks: int
    total_ticks: int
    session_id: str
    window_start: str
    window_end: str


class SensorHealthDetail(BaseModel):
    sensor_id: str
    sensor_identifier: str
    mttr_seconds: float | None
    auto_recovery_time_seconds: float | None
    mtbf_with_auto_recovery_seconds: float | None
    mtbf_without_auto_recovery_seconds: float | None
    failure_count: int
    auto_recovery_count: int
    manual_recovery_count: int
    window_start: str
    window_end: str


class AggregateHealthDetail(BaseModel):
    avg_mttr_seconds: float | None
    avg_auto_recovery_time_seconds: float | None
    avg_mtbf_with_auto_recovery_seconds: float | None
    avg_mtbf_without_auto_recovery_seconds: float | None
    total_sensors: int
    window_start: str
    window_end: str


class SurveillanceMetricsDetail(BaseModel):
    heartbeat_rates: list[HeartbeatRateDetail]
    heartbeat_delivery_probabilities: list[HeartbeatDeliveryProbabilityDetail]
    track_update_probabilities: list[TrackUpdateProbabilityDetail]
    per_sensor_health: list[SensorHealthDetail]
    aggregate_health: AggregateHealthDetail
    active_sessions: int
    window_start: str
    window_end: str
