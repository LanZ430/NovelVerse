from typing import Dict, Any, List, Type, Optional
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class AgentCoordinator:
    """代理协调器，负责管理和协调各个代理的工作"""
    
    def __init__(self):
        """初始化代理协调器"""
        self.agents: Dict[str, BaseAgent] = {}
        self.pipeline: List[str] = []
        self.context: Dict[str, Any] = {}
        logger.info("初始化代理协调器")
    
    def register_agent(self, agent_name: str, agent_instance: BaseAgent) -> None:
        """注册代理
        
        Args:
            agent_name: 代理名称
            agent_instance: 代理实例
        """
        self.agents[agent_name] = agent_instance
        logger.info(f"注册代理: {agent_name}")
    
    def set_pipeline(self, pipeline: List[str]) -> None:
        """设置代理执行管道
        
        Args:
            pipeline: 代理名称列表，按执行顺序排列
        """
        # 验证管道中的所有代理都已注册
        for agent_name in pipeline:
            if agent_name not in self.agents:
                raise ValueError(f"代理 {agent_name} 未注册")
        
        self.pipeline = pipeline
        logger.info(f"设置代理执行管道: {pipeline}")
    
    def initialize_all_agents(self) -> bool:
        """初始化所有注册的代理
        
        Returns:
            bool: 初始化是否全部成功
        """
        all_success = True
        for agent_name, agent in self.agents.items():
            try:
                success = agent.initialize()
                if not success:
                    logger.error(f"代理 {agent_name} 初始化失败")
                    all_success = False
            except Exception as e:
                logger.exception(f"代理 {agent_name} 初始化出错: {str(e)}")
                all_success = False
        
        return all_success
    
    def execute_pipeline(self, initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """按顺序执行管道中的代理
        
        Args:
            initial_context: 初始上下文数据
            
        Returns:
            Dict[str, Any]: 最终执行结果
        """
        self.context = initial_context or {}
        
        for agent_name in self.pipeline:
            logger.info(f"执行代理: {agent_name}")
            try:
                agent = self.agents[agent_name]
                result = agent.execute(self.context)
                
                # 更新上下文
                if isinstance(result, dict):
                    self.context.update(result)
                else:
                    logger.warning(f"代理 {agent_name} 返回非字典结果: {result}")
                    
            except Exception as e:
                logger.exception(f"代理 {agent_name} 执行出错: {str(e)}")
                self.context["error"] = {
                    "agent": agent_name,
                    "message": str(e)
                }
                break
        
        return self.context
    
    def execute_agent(self, agent_name: str, custom_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行单个指定的代理
        
        Args:
            agent_name: 代理名称
            custom_context: 自定义上下文，如果为None则使用当前上下文
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        if agent_name not in self.agents:
            raise ValueError(f"代理 {agent_name} 未注册")
        
        context_to_use = custom_context if custom_context is not None else self.context
        
        try:
            agent = self.agents[agent_name]
            result = agent.execute(context_to_use)
            
            # 如果使用的是当前上下文，更新它
            if custom_context is None and isinstance(result, dict):
                self.context.update(result)
            
            return result
        except Exception as e:
            logger.exception(f"代理 {agent_name} 执行出错: {str(e)}")
            error_result = {
                "status": "error",
                "agent": agent_name,
                "message": str(e)
            }
            
            # 如果使用的是当前上下文，更新错误信息
            if custom_context is None:
                self.context["error"] = error_result
            
            return error_result
    
    def cleanup(self) -> None:
        """清理所有代理资源"""
        for agent_name, agent in self.agents.items():
            try:
                agent.cleanup()
            except Exception as e:
                logger.error(f"清理代理 {agent_name} 出错: {str(e)}")
        
        logger.info("所有代理清理完成") 