from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required
from ..models import Child, DictationTask, DictationTaskItem, DictationConfig, YuwenItem
from ..extensions import db
from ..utils.logger import log_api_call, logger
from ..utils.error_codes import *
import traceback
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import random

dictation_bp = Blueprint('dictation', __name__)

@dictation_bp.route('/api/dictation/config', methods=['GET'])
@jwt_required()
@log_api_call
def get_config():
    """获取听写配置
    
    请求参数:
    - child_id: 必填，孩子ID
    
    返回数据:
    {
        "status": "success",
        "data": {
            "config": {
                "words_per_dictation": 10,
                "review_days": 3,
                "dictation_interval": 5,
                "dictation_ratio": 100,
                "wrong_words_only": false
            }
        }
    }
    """
    try:
        child_id = request.args.get('child_id', type=int)
        if not child_id:
            return jsonify({
                'status': 'error',
                'code': MISSING_REQUIRED_PARAM,
                'message': get_error_message(MISSING_REQUIRED_PARAM, 'child_id')
            }), 400
            
        # 验证孩子所有权
        child = Child.query.filter_by(
            id=child_id,
            user_id=g.user.id
        ).first()
        
        if not child:
            return jsonify({
                'status': 'error',
                'code': CHILD_NOT_FOUND,
                'message': get_error_message(CHILD_NOT_FOUND)
            }), 404
            
        config = child.dictation_config
        if not config:
            config = DictationConfig(child=child)
            db.session.add(config)
            db.session.commit()
            
        return jsonify({
            'status': 'success',
            'data': {
                'config': config.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"获取听写配置失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'code': INTERNAL_ERROR,
            'message': get_error_message(INTERNAL_ERROR)
        }), 500

@dictation_bp.route('/api/dictation/config', methods=['PUT'])
@jwt_required()
@log_api_call
def update_config():
    """更新听写配置
    
    请求参数:
    {
        "child_id": 1,
        "words_per_dictation": 10,
        "review_days": 3,
        "dictation_interval": 5,
        "dictation_ratio": 100,
        "wrong_words_only": false
    }
    """
    try:
        data = request.get_json()
        if not data or 'child_id' not in data:
            return jsonify({
                'status': 'error',
                'code': MISSING_REQUIRED_PARAM,
                'message': get_error_message(MISSING_REQUIRED_PARAM, 'child_id')
            }), 400
            
        # 验证孩子所有权
        child = Child.query.filter_by(
            id=data['child_id'],
            user_id=g.user.id
        ).first()
        
        if not child:
            return jsonify({
                'status': 'error',
                'code': CHILD_NOT_FOUND,
                'message': get_error_message(CHILD_NOT_FOUND)
            }), 404
            
        config = child.dictation_config
        if not config:
            config = DictationConfig(child=child)
            db.session.add(config)
            
        # 更新配置
        for field in [
            'words_per_dictation',
            'review_days',
            'dictation_interval',
            'dictation_ratio',
            'wrong_words_only'
        ]:
            if field in data:
                setattr(config, field, data[field])
                
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"数据库错误: {str(e)}")
            return jsonify({
                'status': 'error',
                'code': DATABASE_ERROR,
                'message': get_error_message(DATABASE_ERROR)
            }), 500
            
        return jsonify({
            'status': 'success',
            'data': {
                'config': config.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"更新听写配置失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'code': INTERNAL_ERROR,
            'message': get_error_message(INTERNAL_ERROR)
        }), 500

@dictation_bp.route('/api/dictation/task/create', methods=['POST'])
@jwt_required()
@log_api_call
def create_task():
    """创建听写任务
    
    请求参数:
    {
        "child_id": 1,
        "unit": 1,          # 可选，指定单元
        "words": ["你好"]   # 可选，指定词语
    }
    """
    try:
        data = request.get_json()
        if not data or 'child_id' not in data:
            return jsonify({
                'status': 'error',
                'code': MISSING_REQUIRED_PARAM,
                'message': get_error_message(MISSING_REQUIRED_PARAM, 'child_id')
            }), 400
            
        # 验证孩子所有权
        child = Child.query.filter_by(
            id=data['child_id'],
            user_id=g.user.id
        ).first()
        
        if not child:
            return jsonify({
                'status': 'error',
                'code': CHILD_NOT_FOUND,
                'message': get_error_message(CHILD_NOT_FOUND)
            }), 404
            
        # 获取配置
        config = child.dictation_config
        if not config:
            config = DictationConfig(child=child)
            db.session.add(config)
            db.session.commit()
            
        # 创建任务
        task = DictationTask(
            child=child,
            user_id=g.user.id
        )
        db.session.add(task)
        
        # 选择词语
        words = []
        if 'words' in data:
            # 使用指定词语
            words = data['words']
        elif 'unit' in data:
            # 从指定单元选择
            items = YuwenItem.query.filter_by(
                grade=child.grade,
                semester=child.semester,
                textbook_version=child.textbook_version,
                unit=data['unit']
            ).all()
            words = [item.word for item in items]
            
            # 随机选择指定数量
            if len(words) > config.words_per_dictation:
                words = random.sample(words, config.words_per_dictation)
        else:
            # 智能选择
            # TODO: 实现智能选择逻辑
            pass
            
        # 创建任务项
        for word in words:
            item = DictationTaskItem(
                task=task,
                word=word
            )
            db.session.add(item)
            
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"数据库错误: {str(e)}")
            return jsonify({
                'status': 'error',
                'code': DATABASE_ERROR,
                'message': get_error_message(DATABASE_ERROR)
            }), 500
            
        return jsonify({
            'status': 'success',
            'data': {
                'task': task.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"创建听写任务失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'code': INTERNAL_ERROR,
            'message': get_error_message(INTERNAL_ERROR)
        }), 500 