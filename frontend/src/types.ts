export interface Run { id: string; game_name: string; current_stage: string; status: string }
export interface ProgressMsg { type: 'progress' | 'gate' | 'ask_user' | 'error'; [k: string]: any }
