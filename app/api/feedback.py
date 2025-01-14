from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.utils.decorators import log_api_call
from ..models import Feedback
from ..extensions import db
from ..utils.logger import logger
from ..utils.error_codes import *
import traceback
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

feedback_bp = Blueprint('feedback', __name__)

@feedback_bp.route('/feedback/create', methods=['POST'])
@jwt_required()
@log_api_call
def create_feedback():
    """创建反馈
    
    请求参数:
    {
        "type": "bug",          # 反馈类型: bug/suggestion/other
        "content": "xxx",       # 反馈内容
        "contact": "xxx",       # 联系方式（选填）
        "images": ["url1"]      # 图片URL列表（选填）
    }
    
    返回数据:
    {
        "status": "success",
        "data": {
            "feedback": {
                "id": 1,
                "type": "bug",
                "content": "xxx",
                "status": "pending",
                "created_at": "2024-01-07T12:00:00Z"
            }
        }
    }
    """
    try:
        # 开启事务
        db.session.begin_nested()
        data = request.get_json()
        user_id = get_jwt_identity()
        
        try:
            # 创建反馈
            feedback = Feedback(
                user_id=user_id,
                title=data['title'],
                content=data['content'],
                type=data.get('type', 'general')
            )
            
            db.session.add(feedback)
            db.session.flush()
            
            # 提交事务
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'data': {
                    'feedback': feedback.to_dict()
                }
            })
        except Exception as e:
            db.session.rollback()
            raise e
            
    except Exception as e:
        logger.error(f"创建反馈失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'code': INTERNAL_ERROR,
            'message': get_error_message(INTERNAL_ERROR)
        }), 500

@feedback_bp.route('/feedback/list', methods=['GET'])
@jwt_required()
@log_api_call
def get_feedback_list():
    """获取反馈列表
    
    请求参数:
    - page: 选填，页码（默认1）
    - per_page: 选填，每页数量（默认20）
    - status: 选填，状态(pending/processing/resolved)
    
    返回数据:
    {
        "status": "success",
        "data": {
            "feedbacks": [{
                "id": 1,
                "type": "bug",
                "content": "xxx",
                "status": "pending",
                "created_at": "2024-01-07T12:00:00Z",
                "reply_count": 2
            }],
            "total": 100,
            "page": 1,
            "pages": 5
        }
    }
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        
        # 构建查询
        query = Feedback.query.filter_by(user_id=int(get_jwt_identity()))
        
        if status:
            query = query.filter_by(status=status)
            
        # 分页
        pagination = query.order_by(
            Feedback.created_at.desc()
        ).paginate(
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'status': 'success',
            'data': {
                'feedbacks': [f.to_dict() for f in pagination.items],
                'total': pagination.total,
                'page': page,
                'pages': pagination.pages
            }
        })
        
    except Exception as e:
        logger.error(f"获取反馈列表失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'code': INTERNAL_ERROR,
            'message': get_error_message(INTERNAL_ERROR)
        }), 500

@feedback_bp.route('/feedback/<int:feedback_id>/detail', methods=['GET'])
@jwt_required()
@log_api_call
def get_feedback_detail(feedback_id):
    """获取反馈详情
    
    返回数据:
    {
        "status": "success",
        "data": {
            "feedback": {
                "id": 1,
                "type": "bug",
                "content": "xxx",
                "status": "pending",
                "created_at": "2024-01-07T12:00:00Z",
                "replies": [{
                    "id": 1,
                    "content": "xxx",
                    "created_at": "2024-01-07T12:00:00Z",
                    "is_admin": true
                }]
            }
        }
    }
    """
    try:
        # 验证所有权
        feedback = Feedback.query.filter_by(
            id=feedback_id,
            user_id=int(get_jwt_identity())
        ).first()
        
        if not feedback:
            return jsonify({
                'status': 'error',
                'code': RESOURCE_NOT_FOUND,
                'message': get_error_message(RESOURCE_NOT_FOUND)
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': {
                'feedback': feedback.to_dict(with_replies=True)
            }
        })
        
    except Exception as e:
        logger.error(f"获取反馈详情失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'code': INTERNAL_ERROR,
            'message': get_error_message(INTERNAL_ERROR)
        }), 500 