import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/search/search_bloc.dart';
import '../widgets/article_card.dart';

/// 搜索页面
class SearchPage extends StatefulWidget {
  const SearchPage({Key? key}) : super(key: key);
  
  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  
  @override
  void initState() {
    super.initState();
    
    // 设置滚动监听，实现无限滚动
    _scrollController.addListener(() {
      if (_scrollController.position.pixels >= 
          _scrollController.position.maxScrollExtent - 200) {
        // 距离底部200像素时开始加载更多
        context.read<SearchBloc>().add(const LoadMoreSearchResults());
      }
    });
  }
  
  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _searchController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: '搜索资讯...',
            border: InputBorder.none,
            hintStyle: TextStyle(color: Colors.grey),
          ),
          style: Theme.of(context).textTheme.titleMedium,
          onSubmitted: (query) {
            if (query.trim().isNotEmpty) {
              _performSearch(query.trim());
            }
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              final query = _searchController.text.trim();
              if (query.isNotEmpty) {
                _performSearch(query);
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.clear),
            onPressed: () {
              _searchController.clear();
              context.read<SearchBloc>().add(const ClearSearch());
            },
          ),
        ],
      ),
      body: BlocBuilder<SearchBloc, SearchState>(
        builder: (context, state) {
          return _buildBody(state);
        },
      ),
    );
  }
  
  Widget _buildBody(SearchState state) {
    if (state is SearchInitial) {
      return _buildInitialWidget();
    }
    
    if (state is SearchLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    
    if (state is SearchError) {
      return _buildErrorWidget(state.message);
    }
    
    if (state is SearchLoaded) {
      return _buildSearchResults(state);
    }
    
    return const SizedBox.shrink();
  }
  
  Widget _buildInitialWidget() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.search,
            size: 64,
            color: Colors.grey,
          ),
          SizedBox(height: 16),
          Text(
            '输入关键词搜索资讯',
            style: TextStyle(
              fontSize: 18,
              color: Colors.grey,
            ),
          ),
          SizedBox(height: 8),
          Text(
            '支持搜索标题、描述和关键词',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey,
            ),
          ),
        ],
      ),
    );
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
            '搜索失败',
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
              final query = _searchController.text.trim();
              if (query.isNotEmpty) {
                _performSearch(query);
              }
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }
  
  Widget _buildSearchResults(SearchLoaded state) {
    return Column(
      children: [
        // 搜索结果提示
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          color: Theme.of(context).colorScheme.surface,
          child: Text(
            '找到 ${state.pagination.totalItems} 条关于 \"${state.query}\" 的结果',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).textTheme.bodySmall?.color,
            ),
          ),
        ),
        
        // 搜索结果列表
        Expanded(
          child: state.articles.isEmpty 
              ? _buildEmptyResults(state.query)
              : _buildResultsList(state),
        ),
      ],
    );
  }
  
  Widget _buildEmptyResults(String query) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.search_off,
            size: 64,
            color: Colors.grey,
          ),
          const SizedBox(height: 16),
          Text(
            '没有找到相关结果',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            '尝试使用其他关键词搜索',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Colors.grey,
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildResultsList(SearchLoaded state) {
    return ListView.builder(
      controller: _scrollController,
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
  
  /// 执行搜索
  void _performSearch(String query) {
    context.read<SearchBloc>().add(SearchArticles(query: query));
  }
}