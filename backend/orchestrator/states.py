"""阶段与状态枚举。"""
from enum import Enum


class Stage(str, Enum):
    S0_init = "S0_init"
    S1_design = "S1_design"
    S2_art_plan = "S2_art_plan"
    S3_art_gen = "S3_art_gen"
    S4_coding = "S4_coding"
    S5_done = "S5_done"


class StageStatus(str, Enum):
    running = "running"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    not_implemented = "not_implemented"
    done = "done"
