// 采集器相关数据模型

/// 采集器实例
class CollectorInstance {
  final String instanceId;
  final String? param;
  final String displayName;
  final String status;
  final double healthScore;
  final int runCount;
  final int errorCount;
  final DateTime? lastRun;
  final DateTime createdAt;

  const CollectorInstance({
    required this.instanceId,
    this.param,
    required this.displayName,
    required this.status,
    required this.healthScore,
    required this.runCount,
    required this.errorCount,
    this.lastRun,
    required this.createdAt,
  });

  factory CollectorInstance.fromJson(Map<String, dynamic> json) {
    return CollectorInstance(
      instanceId: json['instance_id'] as String,
      param: json['param'] as String?,
      displayName: json['display_name'] as String,
      status: json['status'] as String,
      healthScore: (json['health_score'] as num).toDouble(),
      runCount: json['run_count'] as int,
      errorCount: json['error_count'] as int,
      lastRun: json['last_run'] != null
          ? DateTime.parse(json['last_run'] as String)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'instance_id': instanceId,
      'param': param,
      'display_name': displayName,
      'status': status,
      'health_score': healthScore,
      'run_count': runCount,
      'error_count': errorCount,
      'last_run': lastRun?.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is CollectorInstance && other.instanceId == instanceId;
  }

  @override
  int get hashCode => instanceId.hashCode;

  @override
  String toString() {
    return 'CollectorInstance(instanceId: $instanceId, displayName: $displayName)';
  }
}

/// 采集器类型
class CollectorType {
  final String collectorName;
  final String displayName;
  final int totalInstances;
  final List<CollectorInstance> instances;

  const CollectorType({
    required this.collectorName,
    required this.displayName,
    required this.totalInstances,
    required this.instances,
  });

  factory CollectorType.fromJson(Map<String, dynamic> json) {
    return CollectorType(
      collectorName: json['collector_name'] as String,
      displayName: json['display_name'] as String,
      totalInstances: json['total_instances'] as int,
      instances: (json['instances'] as List<dynamic>)
          .map(
            (item) => CollectorInstance.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'collector_name': collectorName,
      'display_name': displayName,
      'total_instances': totalInstances,
      'instances': instances.map((instance) => instance.toJson()).toList(),
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is CollectorType && other.collectorName == collectorName;
  }

  @override
  int get hashCode => collectorName.hashCode;

  @override
  String toString() {
    return 'CollectorType(collectorName: $collectorName, displayName: $displayName, totalInstances: $totalInstances)';
  }
}

/// 采集器响应
class CollectorsResponse {
  final int totalCollectors;
  final Map<String, CollectorType> collectors;

  const CollectorsResponse({
    required this.totalCollectors,
    required this.collectors,
  });

  factory CollectorsResponse.fromJson(Map<String, dynamic> json) {
    final collectorsMap = <String, CollectorType>{};
    final collectorsData = json['collectors'] as Map<String, dynamic>;

    for (final entry in collectorsData.entries) {
      collectorsMap[entry.key] = CollectorType.fromJson(
        entry.value as Map<String, dynamic>,
      );
    }

    return CollectorsResponse(
      totalCollectors: json['total_collectors'] as int,
      collectors: collectorsMap,
    );
  }

  Map<String, dynamic> toJson() {
    final collectorsMap = <String, dynamic>{};
    for (final entry in collectors.entries) {
      collectorsMap[entry.key] = entry.value.toJson();
    }

    return {'total_collectors': totalCollectors, 'collectors': collectorsMap};
  }

  /// 获取所有采集器类型的列表
  List<CollectorType> get collectorTypes => collectors.values.toList();

  @override
  String toString() {
    return 'CollectorsResponse(totalCollectors: $totalCollectors, collectors: ${collectors.length})';
  }
}
