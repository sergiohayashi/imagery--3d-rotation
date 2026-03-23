from abc import ABC

from app.config.global_config import the_global_config
from app.config.config import config


class CommandBase(ABC):
    project_id = "68d0617c5f83766eeb6abb15"
    spatialviz_root_path = the_global_config.data_root_dir / "spatialviz"

    def __init__(self):
        config.user_info_var.set(
            {
                "user_id": "68d0608ad04abf90559d3b75",
                "tenant_id": "pseudo-144cfa41-38ba-4f3f-a184-dc862aa1bc2b",
                "email": None,
                "name": None,
                "is_superuser": True,
                "is_manager": True,
            }
        )
