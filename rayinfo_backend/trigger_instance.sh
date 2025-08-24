#!/bin/bash

# RayInfo 采集器实例手动触发脚本
# 
# 使用方法:
#   1. 列出所有实例: ./trigger_instance.sh list
#   2. 触发指定实例: ./trigger_instance.sh trigger <instance_id>
#   3. 查看帮助: ./trigger_instance.sh help
#
# 示例:
#   ./trigger_instance.sh list
#   ./trigger_instance.sh trigger a1b2c3d4

# 默认API地址，可通过环境变量RAYINFO_API_URL覆盖
API_URL="${RAYINFO_API_URL:-http://localhost:8000}"

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查API连接
check_api() {
    print_info "检查API连接: $API_URL"
    if curl -s -f "$API_URL/" > /dev/null 2>&1; then
        print_success "API连接正常"
        return 0
    else
        print_error "无法连接到API: $API_URL"
        print_error "请确保后端服务正在运行，或设置环境变量 RAYINFO_API_URL"
        return 1
    fi
}

# 列出所有实例
list_instances() {
    print_info "获取采集器实例列表..."
    
    response=$(curl -s "$API_URL/instances")
    if [ $? -ne 0 ]; then
        print_error "请求失败"
        return 1
    fi
    
    # 使用 jq 美化输出（如果可用）
    if command -v jq &> /dev/null; then
        echo "$response" | jq '.'
        
        # 提取实例ID列表便于复制使用
        echo
        print_info "可用的实例ID:"
        echo "$response" | jq -r '.instances | keys[]' | while read -r id; do
            collector_name=$(echo "$response" | jq -r ".instances[\"$id\"].collector_name")
            param=$(echo "$response" | jq -r ".instances[\"$id\"].param")
            if [ "$param" != "null" ]; then
                echo "  $id  ($collector_name:$param)"
            else
                echo "  $id  ($collector_name)"
            fi
        done
    else
        echo "$response"
        print_warning "安装 jq 可获得更好的JSON显示效果"
    fi
}

# 触发指定实例
trigger_instance() {
    local instance_id="$1"
    
    if [ -z "$instance_id" ]; then
        print_error "请提供实例ID"
        echo "用法: $0 trigger <instance_id>"
        return 1
    fi
    
    print_info "触发实例: $instance_id"
    
    response=$(curl -s -w "%{http_code}" "$API_URL/trigger/$instance_id")
    http_code="${response: -3}"
    body="${response:0:${#response}-3}"
    
    case "$http_code" in
        200)
            print_success "实例触发成功"
            if command -v jq &> /dev/null; then
                echo "$body" | jq '.'
            else
                echo "$body"
            fi
            ;;
        404)
            print_error "实例不存在: $instance_id"
            echo "请使用 '$0 list' 查看可用实例"
            ;;
        500)
            print_error "服务器内部错误"
            if command -v jq &> /dev/null; then
                echo "$body" | jq -r '.detail'
            else
                echo "$body"
            fi
            ;;
        503)
            print_error "调度器未初始化，请检查后端服务状态"
            ;;
        *)
            print_error "请求失败 (HTTP $http_code)"
            echo "$body"
            ;;
    esac
}

# 显示帮助信息
show_help() {
    cat << EOF
RayInfo 采集器实例手动触发工具

用法:
    $0 <command> [arguments]

命令:
    list                     列出所有已注册的采集器实例
    trigger <instance_id>    手动触发指定实例执行数据收集
    help                     显示此帮助信息

示例:
    # 列出所有实例
    $0 list
    
    # 触发ID为 a1b2c3d4 的实例
    $0 trigger a1b2c3d4
    
    # 使用自定义API地址
    RAYINFO_API_URL=http://example.com:8000 $0 list

配置:
    RAYINFO_API_URL         API地址 (默认: http://localhost:8000)

注意:
    - 确保RayInfo后端服务正在运行
    - 实例ID可通过 list 命令获取
    - 建议安装 jq 以获得更好的JSON显示效果

EOF
}

# 主函数
main() {
    case "${1:-help}" in
        list)
            if check_api; then
                list_instances
            fi
            ;;
        trigger)
            if check_api; then
                trigger_instance "$2"
            fi
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"