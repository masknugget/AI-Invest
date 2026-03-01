"""
推荐服务模块
"""

from .recommendation_service import RecommendationAppService, get_recommendation_service
from .user_profile_service import UserProfileService, get_user_profile_service

__all__ = [
    'RecommendationAppService',
    'get_recommendation_service',
    'UserProfileService',
    'get_user_profile_service',
]
