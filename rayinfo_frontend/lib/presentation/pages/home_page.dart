import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/articles/articles_bloc.dart';
import '../bloc/articles/articles_event.dart';
import '../bloc/articles/articles_state.dart';
import '../bloc/read_status/read_status_bloc.dart';
import '../bloc/read_status/read_status_state.dart';
import '../bloc/collectors/collectors_bloc.dart';
import '../bloc/collectors/collectors_event.dart';
import '../widgets/article_card.dart';
import '../widgets/collector_type_sidebar.dart';
import '../widgets/collector_instances_list.dart';
import '../../data/models/read_status_models.dart';
import '../../data/models/collector_models.dart';

/// 首页 - 资讯列表
class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final ScrollController _scrollController = ScrollController();

  // 筛选状态
  ReadStatusFilter _currentReadStatus = ReadStatusFilter.unread;
  CollectorType? _selectedCollectorType;
  CollectorInstance? _selectedInstance;

  // 侧边栏状态
  bool _isSidebarCollapsed = false;

  @override
  void initState() {
    super.initState();

    // 初始加载数据（默认只加载未读资讯）
    context.read<ArticlesBloc>().add(
      const LoadArticles(readStatus: ReadStatusFilter.unread),
    );

    // 设置滚动监听，实现无限滚动
    _scrollController.addListener(() {
      if (_scrollController.position.pixels >=
          _scrollController.position.maxScrollExtent - 200) {
        // 距离底部200像素时开始加载更多
        context.read<ArticlesBloc>().add(const LoadMoreArticles());
      }
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<ReadStatusBloc, ReadStatusState>(
        listener: (context, readStatusState) {
          // 监听已读状态变化，同步更新文章列表
          if (readStatusState is ReadStatusSuccess) {
            context.read<ArticlesBloc>().updateArticleStatus(
              readStatusState.postId,
              readStatusState.isRead,
              readStatusState.readAt,
            );
          } else if (readStatusState is BatchReadStatusSuccess) {
            // 处理批量操作成功的情况，重新加载当前页面
            context.read<ArticlesBloc>().add(
              RefreshArticles(
                readStatus: _currentReadStatus,
                instanceId: _selectedInstance?.instanceId,
              ),
            );
          }
        },
        child: _buildResponsiveLayout(context),
      ),
    );
  }

  /// 构建响应式布局
  Widget _buildResponsiveLayout(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth >= 768;

    return Row(
      children: [
        // 左侧边栏 - 采集器类型
        if (isDesktop || !_isSidebarCollapsed)
          CollectorTypeSidebar(
            selectedCollectorType: _selectedCollectorType,
            selectedReadStatus: _currentReadStatus,
            onCollectorTypeChanged: _onCollectorTypeChanged,
            onReadStatusChanged: _onReadStatusChanged,
            onSearchPressed: () {
              Navigator.pushNamed(context, '/search');
            },
            isCollapsed: _isSidebarCollapsed && screenWidth < 1024,
            onToggleCollapse: isDesktop
                ? null
                : () {
                    setState(() {
                      _isSidebarCollapsed = !_isSidebarCollapsed;
                    });
                  },
          ),

        // 中间列 - 采集器实例列表
        if ((isDesktop || !_isSidebarCollapsed) &&
            _selectedCollectorType != null)
          CollectorInstancesList(
            selectedCollectorType: _selectedCollectorType,
            selectedInstanceId: _selectedInstance?.instanceId,
            onInstanceSelected: _onInstanceSelected,
            onRefresh: () {
              context.read<CollectorsBloc>().add(const RefreshCollectors());
            },
          ),

        // 主内容区域
        Expanded(
          child: Stack(
            children: [
              BlocBuilder<ArticlesBloc, ArticlesState>(
                builder: (context, state) {
                  return RefreshIndicator(
                    onRefresh: () async {
                      // 根据当前选择状态刷新文章
                      if (_selectedInstance != null) {
                        context.read<ArticlesBloc>().add(
                          RefreshArticles(
                            readStatus: _currentReadStatus,
                            instanceId: _selectedInstance!.instanceId,
                          ),
                        );
                      } else if (_selectedCollectorType != null) {
                        context.read<ArticlesBloc>().add(
                          RefreshArticles(
                            readStatus: _currentReadStatus,
                            source: _selectedCollectorType!.collectorName,
                          ),
                        );
                      } else {
                        context.read<ArticlesBloc>().add(
                          RefreshArticles(readStatus: _currentReadStatus),
                        );
                      }
                    },
                    child: _buildMainContent(state),
                  );
                },
              ),

              // 在小屏幕上显示侧边栏切换按钮（悬浮按钮）
              if (screenWidth < 768)
                Positioned(
                  top: 16,
                  left: 16,
                  child: FloatingActionButton(
                    mini: true,
                    onPressed: () {
                      setState(() {
                        _isSidebarCollapsed = !_isSidebarCollapsed;
                      });
                    },
                    tooltip: _isSidebarCollapsed ? '显示侧边栏' : '隐藏侧边栏',
                    child: Icon(
                      _isSidebarCollapsed ? Icons.menu : Icons.menu_open,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  /// 处理采集器类型变化
  void _onCollectorTypeChanged(CollectorType? collectorType) {
    setState(() {
      _selectedCollectorType = collectorType;
      _selectedInstance = null; // 清除之前选择的实例
    });
    // 当选择采集器类型时，加载所有该类型的文章
    if (collectorType != null) {
      context.read<ArticlesBloc>().add(
        LoadArticles(
          page: 1,
          readStatus: _currentReadStatus,
          source: collectorType.collectorName,
        ),
      );
    } else {
      // 如果没有选择采集器类型，加载所有文章
      context.read<ArticlesBloc>().add(
        LoadArticles(page: 1, readStatus: _currentReadStatus),
      );
    }
  }

  /// 处理采集器实例选择
  void _onInstanceSelected(CollectorInstance instance) {
    setState(() {
      _selectedInstance = instance;
    });
    // 根据实例ID加载对应的文章
    context.read<ArticlesBloc>().add(
      LoadArticles(
        page: 1,
        readStatus: _currentReadStatus,
        instanceId: instance.instanceId,
      ),
    );
  }

  /// 处理已读状态变化
  void _onReadStatusChanged(ReadStatusFilter readStatus) {
    setState(() {
      _currentReadStatus = readStatus;
    });

    // 根据当前选择状态加载文章
    if (_selectedInstance != null) {
      // 如果有选择的实例，使用 instanceId
      context.read<ArticlesBloc>().add(
        LoadArticles(
          page: 1,
          readStatus: readStatus,
          instanceId: _selectedInstance!.instanceId,
        ),
      );
    } else if (_selectedCollectorType != null) {
      // 如果有选择的采集器类型，使用 source
      context.read<ArticlesBloc>().add(
        LoadArticles(
          page: 1,
          readStatus: readStatus,
          source: _selectedCollectorType!.collectorName,
        ),
      );
    } else {
      // 没有任何选择，加载所有文章
      context.read<ArticlesBloc>().add(
        LoadArticles(page: 1, readStatus: readStatus),
      );
    }
  }

  Widget _buildMainContent(ArticlesState state) {
    if (state is ArticlesLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state is ArticlesError) {
      return _buildErrorWidget(state.message);
    }

    if (state is ArticlesLoaded) {
      return _buildArticlesList(state);
    }

    return const Center(child: Text('暂无数据'));
  }

  Widget _buildErrorWidget(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 16),
          Text('加载失败', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            message,
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () {
              // 根据当前选择状态重新加载文章
              if (_selectedInstance != null) {
                context.read<ArticlesBloc>().add(
                  LoadArticles(
                    readStatus: _currentReadStatus,
                    instanceId: _selectedInstance!.instanceId,
                  ),
                );
              } else if (_selectedCollectorType != null) {
                context.read<ArticlesBloc>().add(
                  LoadArticles(
                    readStatus: _currentReadStatus,
                    source: _selectedCollectorType!.collectorName,
                  ),
                );
              } else {
                context.read<ArticlesBloc>().add(
                  LoadArticles(readStatus: _currentReadStatus),
                );
              }
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildArticlesList(ArticlesLoaded state) {
    if (state.articles.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.article_outlined, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('暂无资讯', style: TextStyle(fontSize: 18, color: Colors.grey)),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: state.articles.length + (state.isLoadingMore ? 1 : 0),
      itemBuilder: (context, index) {
        // 显示加载更多指示器
        if (index == state.articles.length) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator()),
          );
        }

        final article = state.articles[index];
        return ArticleCard(article: article);
      },
    );
  }
}
