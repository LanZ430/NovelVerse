from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseAgent:
    """所有代理的基类，定义通用的接口和功能"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化代理
        
        Args:
            config: 代理配置
        """
        self.config = config or {}
        self.name = self.__class__.__name__
        self.is_initialized = False
        logger.info(f"初始化代理: {self.name}")
    
    def initialize(self) -> bool:
        """初始化代理资源和连接
        
        Returns:
            bool: 初始化是否成功
        """
        self.is_initialized = True
        logger.info(f"代理 {self.name} 初始化成功")
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行代理功能
        
        Args:
            context: 上下文信息
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        if not self.is_initialized:
            self.initialize()
        
        logger.info(f"代理 {self.name} 开始执行")
        return {"status": "success", "message": f"{self.name} executed"}
    
    def cleanup(self) -> None:
        """清理代理资源"""
        self.is_initialized = False
        logger.info(f"代理 {self.name} 清理完成") 