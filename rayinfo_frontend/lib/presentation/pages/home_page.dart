import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/articles/articles_bloc.dart';
import '../bloc/articles/articles_event.dart';
import '../bloc/articles/articles_state.dart';
import '../widgets/article_card.dart';
import '../widgets/article_filter_bar.dart';
import '../../data/models/read_status_models.dart';

/// 首页 - 资讯列表
class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);
  
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final ScrollController _scrollController = ScrollController();
  
  // 筛选状态
  ReadStatusFilter _currentReadStatus = ReadStatusFilter.all;
  String? _currentSource;
  bool _showFilters = false;
  
  @override
  void initState() {
    super.initState();
    
    // 初始加载数据
    context.read<ArticlesBloc>().add(const LoadArticles());
    
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
      appBar: AppBar(
        title: const Text('RayInfo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // TODO: 导航到搜索页面
              Navigator.pushNamed(context, '/search');
            },
          ),
          IconButton(
            icon: Icon(_showFilters ? Icons.filter_list : Icons.filter_list_outlined),
            onPressed: () {
              setState(() {
                _showFilters = !_showFilters;
              });
            },
            tooltip: _showFilters ? '隐藏筛选器' : '显示筛选器',
          ),
        ],
      ),
      body: BlocBuilder<ArticlesBloc, ArticlesState>(
        builder: (context, state) {
          return Column(
            children: [
              // 筛选器（按需显示）
              if (_showFilters)
                _buildFilterSection(state),
              
              // 主内容区域
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () async {
                    context.read<ArticlesBloc>().add(RefreshArticles(
                      readStatus: _currentReadStatus,
                      source: _currentSource,
                    ));
                  },
                  child: _buildBody(state),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
  
  Widget _buildBody(ArticlesState state) {
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
          Text(
            '加载失败',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () {
              context.read<ArticlesBloc>().add(const LoadArticles());
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
  
  /// 构建筛选器区域
  Widget _buildFilterSection(ArticlesState state) {
    // 获取可用的来源列表（可以从状态或API获取）
    final availableSources = <String>[
      'mes.search',
      'weibo.home',
      // 可以根据实际数据动态生成
    ];
    
    return ArticleFilterBar(
      selectedReadStatus: _currentReadStatus,
      selectedSource: _currentSource,
      availableSources: availableSources,
      onReadStatusChanged: (readStatus) {
        setState(() {
          _currentReadStatus = readStatus;
        });
        context.read<ArticlesBloc>().filterByReadStatus(readStatus);
      },
      onSourceChanged: (source) {
        setState(() {
          _currentSource = source;
        });
        context.read<ArticlesBloc>().filterBySource(source);
      },
      onClearFilters: () {
        setState(() {
          _currentReadStatus = ReadStatusFilter.all;
          _currentSource = null;
        });
        context.read<ArticlesBloc>().add(const LoadArticles(
          page: 1,
        ));
      },
    );
  }
}