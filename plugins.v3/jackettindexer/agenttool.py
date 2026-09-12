# -*- coding: utf-8 -*-
"""
Agent tools for JackettIndexer plugin
"""

from typing import Optional, Type

from pydantic import BaseModel

from app.agent.tools.base import MoviePilotTool
from app.sdk.plugins import PluginManager

from .schemas import SearchTorrentsToolInput, ListIndexersToolInput


class SearchTorrentsTool(MoviePilotTool):
    """Jackett搜索种子工具"""

    # 工具名称
    name: str = "jackett_search_torrents"

    # 工具描述
    description: str = (
        "Search for torrents across all Jackett indexers. "
        "Use this when the user wants to find movies or TV shows torrents. "
        "Supports keyword search and IMDb ID search (format: tt1234567). "
        "Can filter by media type (movie/tv) and specific indexer."
    )

    # 输入参数模型
    args_schema: Type[BaseModel] = SearchTorrentsToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        """根据参数生成友好的提示消息"""
        keyword = kwargs.get("keyword", "")
        mtype = kwargs.get("mtype")
        indexer_name = kwargs.get("indexer_name")

        message = f"正在通过Jackett搜索: {keyword}"
        if mtype:
            message += f" (类型: {mtype})"
        if indexer_name:
            message += f" (索引器: {indexer_name})"

        return message

    async def run(
        self,
        keyword: str,
        mtype: str | None = None,
        indexer_name: str | None = None,
        **kwargs
    ) -> str:
        """
        执行种子搜索

        Args:
            keyword: 搜索关键词或IMDb ID
            mtype: 媒体类型 (movie/tv)
            indexer_name: 指定索引器名称
            **kwargs: 其他参数，包含 explanation

        Returns:
            搜索结果的格式化字符串
        """
        try:
            # 获取插件实例
            plugins = PluginManager().running_plugins
            plugin_instance = plugins.get("JackettIndexer")

            if not plugin_instance:
                return "❌ JackettIndexer 插件未运行"

            if not plugin_instance._enabled:
                return "❌ JackettIndexer 插件未启用"

            # 调用插件的搜索API
            results = plugin_instance.api_search(
                keyword=keyword,
                indexer_name=indexer_name,
                mtype=mtype,
                page=0
            )

            if not results:
                return f"📭 未找到结果：关键词 '{keyword}'"

            # 格式化结果（显示前5条）
            max_display = 5
            result_lines = [
                f"✅ 找到 {len(results)} 条结果，显示前 {min(len(results), max_display)} 条：\n"
            ]

            for idx, torrent in enumerate(results[:max_display], 1):
                # 格式化大小
                size_gb = torrent['size'] / (1024**3) if torrent['size'] > 0 else 0

                # 促销标志
                promo = []
                if torrent['downloadvolumefactor'] == 0.0:
                    promo.append("🆓")
                elif torrent['downloadvolumefactor'] == 0.5:
                    promo.append("50%")
                if torrent['uploadvolumefactor'] == 2.0:
                    promo.append("2xUp")
                promo_str = " ".join(promo) if promo else ""

                result_lines.append(
                    f"{idx}. {torrent['title']}\n"
                    f"   大小: {size_gb:.2f}GB | 做种: {torrent['seeders']} | 下载: {torrent['peers']}\n"
                    f"   站点: {torrent['site_name']}"
                )

                # Jackett特有的grabs信息
                if torrent.get('grabs'):
                    result_lines[-1] += f" | 完成: {torrent['grabs']}"

                if promo_str:
                    result_lines.append(f"   促销: {promo_str}")

                result_lines.append("")

            return "\n".join(result_lines)

        except Exception as e:
            return f"❌ 搜索失败: {str(e)}"


class ListIndexersTool(MoviePilotTool):
    """Jackett索引器列表工具"""

    # 工具名称
    name: str = "jackett_list_indexers"

    # 工具描述
    description: str = (
        "List all available Jackett indexers. "
        "Use this when the user wants to know which indexers are registered and available for searching."
    )

    # 输入参数模型
    args_schema: Type[BaseModel] = ListIndexersToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        """根据参数生成友好的提示消息"""
        return "正在获取Jackett索引器列表"

    async def run(self, **kwargs) -> str:
        """
        获取索引器列表

        Args:
            **kwargs: 其他参数，包含 explanation

        Returns:
            索引器列表的格式化字符串
        """
        try:
            # 获取插件实例
            plugins = PluginManager().running_plugins
            plugin_instance = plugins.get("JackettIndexer")

            if not plugin_instance:
                return "❌ JackettIndexer 插件未运行"

            if not plugin_instance._enabled:
                return "❌ JackettIndexer 插件未启用"

            # 获取索引器列表
            indexers = plugin_instance.get_indexers()

            if not indexers:
                return "📋 当前没有已注册的Jackett索引器"

            # 统计信息
            total = len(indexers)
            private_count = sum(1 for idx in indexers
                              if idx.get("privacy", "").lower() not in ["public", "semi-public"])
            semi_private_count = sum(1 for idx in indexers
                                    if idx.get("privacy", "").lower() == "semi-public")

            # 构建列表
            result_lines = [
                f"📋 **Jackett索引器列表**",
                f"共 {total} 个索引器（私有:{private_count} | 半私有:{semi_private_count}）\n"
            ]

            for idx, indexer in enumerate(indexers, 1):
                # 隐私类型标识
                privacy = indexer.get("privacy", "private")
                if privacy.lower() == "public":
                    privacy_icon = "🌐"
                elif privacy.lower() == "semi-public":
                    privacy_icon = "🔓"
                else:
                    privacy_icon = "🔒"

                # 站点名称（去掉插件前缀）
                site_name = indexer.get("name", "Unknown")
                plugin_prefix = "Jackett索引器-"
                if site_name.startswith(plugin_prefix):
                    site_name = site_name[len(plugin_prefix):]

                # 提取索引器名称
                domain = indexer.get("domain", "")
                indexer_name = domain.split(".")[-1] if domain else "N/A"

                result_lines.append(f"{idx}. {privacy_icon} {site_name} ({indexer_name})")

            return "\n".join(result_lines)

        except Exception as e:
            return f"❌ 获取索引器列表失败: {str(e)}"
