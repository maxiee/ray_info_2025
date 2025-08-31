import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/source.dart';
import '../bloc/sources/sources_bloc.dart';
import '../bloc/sources/sources_state.dart';
import '../bloc/sources/sources_event.dart';
import '../../data/models/read_status_models.dart';

/// 左侧来源筛选边栏组件
///
/// 类似RSS阅读器的左侧边栏，显示所有可用的信息来源
/// 支持：
/// - 显示各来源的未读计数
/// - 点击来源进行筛选
/// - 显示所有/未读/已读状态切换
/// - 响应式设计（小屏幕可折叠）
class SourceSidebar extends StatefulWidget {
  final String? selectedSource;
  final ReadStatusFilter selectedReadStatus;
  final Function(String?) onSourceChanged;
  final Function(ReadStatusFilter) onReadStatusChanged;
  final bool isCollapsed;
  final VoidCallback? onToggleCollapse;

  const SourceSidebar({
    super.key,
    this.selectedSource,
    required this.selectedReadStatus,
    required this.onSourceChanged,
    required this.onReadStatusChanged,
    this.isCollapsed = false,
    this.onToggleCollapse,
  });

  @override
  State<SourceSidebar> createState() => _SourceSidebarState();
}

class _SourceSidebarState extends State<SourceSidebar> {
  @override
  void initState() {
    super.initState();
    // 初始化时加载来源数据
    context.read<SourcesBloc>().add(const LoadSources());
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

          // 来源列表
          Expanded(child: _buildSourcesList(context)),
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
          Icon(Icons.source, color: theme.colorScheme.primary, size: 20),
          const SizedBox(width: 8),
          Text(
            '信息来源',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: theme.colorScheme.primary,
            ),
          ),
          const Spacer(),

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

  /// 构建来源列表
  Widget _buildSourcesList(BuildContext context) {
    return BlocBuilder<SourcesBloc, SourcesState>(
      builder: (context, state) {
        if (state is SourcesLoading) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(),
            ),
          );
        }

        if (state is SourcesError) {
          return _buildErrorWidget(context, state.message);
        }

        if (state is SourcesLoaded) {
          return _buildLoadedSourcesList(context, state.sources);
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
              context.read<SourcesBloc>().add(const LoadSources());
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  /// 构建已加载的来源列表
  Widget _buildLoadedSourcesList(BuildContext context, List<Source> sources) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // "全部来源" 选项
          _buildSourceItem(
            context,
            source: null,
            displayName: '全部来源',
            count: sources.fold(0, (sum, source) => sum + source.count),
            isSelected: widget.selectedSource == null,
          ),

          const SizedBox(height: 8),

          // 各个来源
          Expanded(
            child: ListView.builder(
              itemCount: sources.length,
              itemBuilder: (context, index) {
                final source = sources[index];
                return _buildSourceItem(
                  context,
                  source: source.name,
                  displayName: source.displayName,
                  count: source.count,
                  isSelected: widget.selectedSource == source.name,
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  /// 构建单个来源项
  Widget _buildSourceItem(
    BuildContext context, {
    required String? source,
    required String displayName,
    required int count,
    required bool isSelected,
  }) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: InkWell(
        onTap: () => widget.onSourceChanged(source),
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
              // 来源图标
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: source == null
                      ? theme.colorScheme.primary
                      : _getSourceColor(source),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 12),

              // 来源名称
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

              // 计数徽章
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

  /// 获取来源对应的颜色
  Color _getSourceColor(String? source) {
    final theme = Theme.of(context);

    switch (source) {
      case 'mes.search':
        return Colors.blue;
      case 'weibo.home':
        return Colors.orange;
      case 'rss.feed':
        return Colors.green;
      default:
        return theme.colorScheme.primary;
    }
  }
}
