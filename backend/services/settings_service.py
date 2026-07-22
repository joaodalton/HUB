# backend/services/settings_service.py
from extensions import db
from models.setting import Setting


def get_all_settings() -> dict:
    settings = Setting.query.all()
    return {setting.chave: setting.valor for setting in settings}


def update_settings(data: dict) -> dict:
    for chave, valor in data.items():
        setting = Setting.query.filter_by(chave=chave).first()

        if setting:
            setting.valor = valor
        else:
            setting = Setting(chave=chave, valor=valor)
            db.session.add(setting)

    db.session.commit()
    return get_all_settings()