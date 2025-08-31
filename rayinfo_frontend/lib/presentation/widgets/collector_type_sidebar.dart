import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/models/collector_models.dart';
import '../../data/models/read_status_models.dart';
import '../bloc/collectors/collectors_bloc.dart';
import '../bloc/collectors/collectors_state.dart';
import '../bloc/collectors/collectors_event.dart';

/// 采集器类型侧边栏组件
///
/// 显示所有可用的采集器类型，类似于传统RSS阅读器的分类列表
/// 支持：
/// - 显示各采集器类型的实例数量
/// - 点击类型进行选择
/// - 显示所有/未读/已读状态切换
/// - 响应式设计（小屏幕可折叠）
/// - 搜索功能按钮
class CollectorTypeSidebar extends StatefulWidget {
  final CollectorType? selectedCollectorType;
  final ReadStatusFilter selectedReadStatus;
  final Function(CollectorType?) onCollectorTypeChanged;
  final Function(ReadStatusFilter) onReadStatusChanged;
  final bool isCollapsed;
  final VoidCallback? onToggleCollapse;
  final VoidCallback? onSearchPressed;

  const CollectorTypeSidebar({
    super.key,
    this.selectedCollectorType,
    required this.selectedReadStatus,
    required this.onCollectorTypeChanged,
    required this.onReadStatusChanged,
    this.isCollapsed = false,
    this.onToggleCollapse,
    this.onSearchPressed,
  });

  @override
  State<CollectorTypeSidebar> createState() => _CollectorTypeSidebarState();
}

class _CollectorTypeSidebarState extends State<CollectorTypeSidebar> {
  @override
  void initState() {
    super.initState();
    // 初始化时加载采集器数据
    context.read<CollectorsBloc>().add(const LoadCollectors());
  }

  @override
  Widget build(BuildContext context) {
    if (widget.isCollapsed) {
      return _buildCollapsedSidebar(context);
    }

    return _buildExpandedSidebar(context);
  }

  /// 构建折叠状态的侧边栏
  Widget _buildCollapsedSidebar(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: 56,
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(right: BorderSide(color: theme.dividerColor, width: 1)),
      ),
      child: Column(
        children: [
          // 展开按钮
          if (widget.onToggleCollapse != null)
            IconButton(
              onPressed: widget.onToggleCollapse,
              icon: const Icon(Icons.menu),
              tooltip: '展开侧边栏',
            ),

          const SizedBox(height: 8),

          // 筛选状态指示器
          _buildReadStatusIndicators(context, true),
        ],
      ),
    );
  }

  /// 构建展开状态的侧边栏
  Widget _buildExpandedSidebar(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: 280,
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(right: BorderSide(color: theme.dividerColor, width: 1)),
      ),
      child: Column(
        children: [
          // 头部区域
          _buildHeader(context),

          // 已读状态筛选
          _buildReadStatusSection(context),

          const Divider(),

          // 采集器类型列表
          Expanded(child: _buildCollectorTypesList(context)),
        ],
      ),
    );
  }

  /// 构建头部区域
  Widget _buildHeader(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Icon(Icons.storage, color: theme.colorScheme.primary, size: 20),
          const SizedBox(width: 8),
          Text(
            '采集器',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: theme.colorScheme.primary,
            ),
          ),
          const Spacer(),

          // 搜索按钮
          if (widget.onSearchPressed != null)
            IconButton(
              onPressed: widget.onSearchPressed,
              icon: const Icon(Icons.search),
              iconSize: 20,
              tooltip: '搜索',
              style: IconButton.styleFrom(
                backgroundColor: theme.colorScheme.primary.withOpacity(0.1),
                foregroundColor: theme.colorScheme.primary,
              ),
            ),

          const SizedBox(width: 8),

          // 折叠按钮
          if (widget.onToggleCollapse != null)
            IconButton(
              onPressed: widget.onToggleCollapse,
              icon: const Icon(Icons.close),
              iconSize: 20,
              tooltip: '折叠侧边栏',
            ),
        ],
      ),
    );
  }

  /// 构建已读状态筛选区域
  Widget _buildReadStatusSection(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '阅读状态',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w500,
              color: Theme.of(context).colorScheme.outline,
            ),
          ),
          const SizedBox(height: 8),
          _buildReadStatusIndicators(context, false),
        ],
      ),
    );
  }

  /// 构建已读状态指示器
  Widget _buildReadStatusIndicators(BuildContext context, bool isCollapsed) {
    if (isCollapsed) {
      // 折叠状态，只显示当前选中的状态图标
      IconData icon;
      switch (widget.selectedReadStatus) {
        case ReadStatusFilter.all:
          icon = Icons.list;
          break;
        case ReadStatusFilter.unread:
          icon = Icons.circle_outlined;
          break;
        case ReadStatusFilter.read:
          icon = Icons.check_circle_outline;
          break;
      }

      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Icon(
          icon,
          color: Theme.of(context).colorScheme.primary,
          size: 20,
        ),
      );
    }

    // 展开状态，显示所有选项
    return Column(
      children: [
        _buildReadStatusItem(context, ReadStatusFilter.all, '全部', Icons.list),
        _buildReadStatusItem(
          context,
          ReadStatusFilter.unread,
          '未读',
          Icons.circle_outlined,
        ),
        _buildReadStatusItem(
          context,
          ReadStatusFilter.read,
          '已读',
          Icons.check_circle_outline,
        ),
      ],
    );
  }

  /// 构建单个已读状态项
  Widget _buildReadStatusItem(
    BuildContext context,
    ReadStatusFilter filter,
    String label,
    IconData icon,
  ) {
    final theme = Theme.of(context);
    final isSelected = widget.selectedReadStatus == filter;

    return InkWell(
      onTap: () => widget.onReadStatusChanged(filter),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? theme.colorScheme.primary.withOpacity(0.1) : null,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected
                  ? theme.colorScheme.primary
                  : theme.colorScheme.onSurface,
            ),
            const SizedBox(width: 12),
            Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: isSelected
                    ? theme.colorScheme.primary
                    : theme.colorScheme.onSurface,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 构建采集器类型列表
  Widget _buildCollectorTypesList(BuildContext context) {
    return BlocBuilder<CollectorsBloc, CollectorsState>(
      builder: (context, state) {
        if (state is CollectorsLoading) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(),
            ),
          );
        }

        if (state is CollectorsError) {
          return _buildErrorWidget(context, state.message);
        }

        if (state is CollectorsLoaded) {
          return _buildLoadedCollectorTypesList(context, state.collectorTypes);
        }

        return const Center(child: Text('暂无数据'));
      },
    );
  }

  /// 构建错误状态组件
  Widget _buildErrorWidget(BuildContext context, String message) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 32, color: theme.colorScheme.error),
          const SizedBox(height: 8),
          Text(
            '加载失败',
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            message,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.outline,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: () {
              context.read<CollectorsBloc>().add(const LoadCollectors());
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  /// 构建已加载的采集器类型列表
  Widget _buildLoadedCollectorTypesList(
    BuildContext context,
    List<CollectorType> collectorTypes,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // "全部采集器" 选项
          _buildCollectorTypeItem(
            context,
            collectorType: null,
            displayName: '全部采集器',
            count: collectorTypes.fold(
              0,
              (sum, type) => sum + type.totalInstances,
            ),
            isSelected: widget.selectedCollectorType == null,
          ),

          const SizedBox(height: 8),

          // 各个采集器类型
          Expanded(
            child: ListView.builder(
              itemCount: collectorTypes.length,
              itemBuilder: (context, index) {
                final collectorType = collectorTypes[index];
                return _buildCollectorTypeItem(
                  context,
                  collectorType: collectorType,
                  displayName: collectorType.displayName,
                  count: collectorType.totalInstances,
                  isSelected:
                      widget.selectedCollectorType?.collectorName ==
                      collectorType.collectorName,
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  /// 构建单个采集器类型项
  Widget _buildCollectorTypeItem(
    BuildContext context, {
    required CollectorType? collectorType,
    required String displayName,
    required int count,
    required bool isSelected,
  }) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: InkWell(
        onTap: () => widget.onCollectorTypeChanged(collectorType),
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: isSelected
                ? theme.colorScheme.primaryContainer.withOpacity(0.5)
                : null,
            borderRadius: BorderRadius.circular(8),
            border: isSelected
                ? Border.all(
                    color: theme.colorScheme.primary.withOpacity(0.3),
                    width: 1,
                  )
                : null,
          ),
          child: Row(
            children: [
              // 采集器类型图标
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: collectorType == null
                      ? theme.colorScheme.primary
                      : _getCollectorTypeColor(collectorType.collectorName),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 12),

              // 采集器类型名称
              Expanded(
                child: Text(
                  displayName,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: isSelected
                        ? theme.colorScheme.primary
                        : theme.colorScheme.onSurface,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),

              // 实例数量徽章
              if (count > 0)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? theme.colorScheme.primary
                        : theme.colorScheme.outline.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    count.toString(),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: isSelected
                          ? theme.colorScheme.onPrimary
                          : theme.colorScheme.outline,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  /// 获取采集器类型对应的颜色
  Color _getCollectorTypeColor(String collectorName) {
    switch (collectorName) {
      case 'mes.search':
        return Colors.blue;
      case 'weibo.home':
        return Colors.orange;
      case 'rss.feed':
        return Colors.green;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }
}
