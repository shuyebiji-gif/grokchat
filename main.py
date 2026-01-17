#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grok聊天APP（适配Android 14 + 体验优化版）
优化点：1. 自定义API地址 2. 分类异常提示 3. 系统提示初始化
"""
import json
import asyncio
import aiohttp
import datetime
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import mainthread
from plyer import clipboard

# 全局配置
WINDOW_WIDTH = Window.width
WINDOW_HEIGHT = Window.height

# ========== 适配Android 14：Kivy私有目录 ==========
DATA_DIR = ""  # 初始化空值，在App启动时赋值
API_KEY_FILE = ""
API_URL_FILE = ""  # 新增：存储自定义API地址
SESSIONS_FILE = ""

# 初始化默认数据（新增API地址配置）
def init_default_data(app_instance):
    global DATA_DIR, API_KEY_FILE, API_URL_FILE, SESSIONS_FILE
    # 赋值为App的私有目录（适配Android 14）
    DATA_DIR = app_instance.user_data_dir
    API_KEY_FILE = os.path.join(DATA_DIR, "api_key.json")
    API_URL_FILE = os.path.join(DATA_DIR, "api_url.json")  # 新增
    SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
    
    # 确保目录存在（私有目录无需权限）
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # 初始化API密钥文件
    if not os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "w", encoding="utf-8") as f:
            json.dump({"api_key": ""}, f)
    
    # ========== 优化1：初始化API地址文件（默认官方地址） ==========
    if not os.path.exists(API_URL_FILE):
        default_api_url = "https://api.x.ai/v1/chat/completions"
        with open(API_URL_FILE, "w", encoding="utf-8") as f:
            json.dump({"api_url": default_api_url}, f)
    
    # ========== 优化3：初始化会话文件（加入system prompt） ==========
    if not os.path.exists(SESSIONS_FILE):
        default_session = {
            "id": "default",
            "name": "默认会话",
            "last_msg": "暂无消息",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "messages": [],
            # 新增system prompt（Grok-1支持则生效，不支持则忽略）
            "context": [{"role": "system", "content": "You are a helpful assistant. Answer questions clearly and concisely."}]
        }
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"current_session": "default", "sessions": [default_session]}, f)

# 读取API密钥
def get_api_key():
    with open(API_KEY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("api_key", "")

# 保存API密钥
def save_api_key(api_key):
    with open(API_KEY_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key}, f)

# ========== 优化1：新增API地址读取/保存函数 ==========
def get_api_url():
    with open(API_URL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("api_url", "https://api.x.ai/v1/chat/completions")

def save_api_url(api_url):
    with open(API_URL_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_url": api_url}, f)

# 会话管理类（无修改，保持原有功能）
class SessionManager:
    def __init__(self):
        self.load_sessions()

    def load_sessions(self):
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.current_session_id = self.data["current_session"]
        self.sessions = self.data["sessions"]

    def save_sessions(self):
        self.data["current_session"] = self.current_session_id
        self.data["sessions"] = self.sessions
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_current_session(self):
        return next(s for s in self.sessions if s["id"] == self.current_session_id)

    def create_session(self, first_msg="新会话"):
        session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_session = {
            "id": session_id,
            "name": first_msg[:20],
            "last_msg": first_msg[:30],
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "messages": [],
            # 新会话也加入system prompt
            "context": [{"role": "system", "content": "You are a helpful assistant. Answer questions clearly and concisely."}]
        }
        self.sessions.append(new_session)
        self.current_session_id = session_id
        self.save_sessions()
        return session_id

    def rename_session(self, session_id, new_name):
        session = next(s for s in self.sessions if s["id"] == session_id)
        session["name"] = new_name
        self.save_sessions()

    def delete_session(self, session_id):
        if session_id == "default":
            return False
        self.sessions = [s for s in self.sessions if s["id"] != session_id]
        self.current_session_id = "default"
        self.save_sessions()
        return True

    def update_session_msg(self, session_id, user_msg, grok_msg):
        session = next(s for s in self.sessions if s["id"] == session_id)
        session["messages"].append({
            "role": "user",
            "content": user_msg,
            "time": datetime.datetime.now().strftime("%H:%M")
        })
        session["messages"].append({
            "role": "grok",
            "content": grok_msg,
            "time": datetime.datetime.now().strftime("%H:%M")
        })
        session["context"].append({"role": "user", "content": user_msg})
        session["context"].append({"role": "assistant", "content": grok_msg})
        if len(session["context"]) > 20:
            session["context"] = session["context"][-20:]
        session["last_msg"] = user_msg[:30]
        session["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.save_sessions()

# 消息气泡组件（无修改）
class MessageBubble(Label):
    def __init__(self, content, role, time, **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.role = role
        self.time = time
        self.font_size = 14
        self.size_hint_y = None
        self.bind(texture_size=self.setter('size'))
        self.padding = [10, 8, 10, 8]
        self.markup = True

        with self.canvas.before:
            if role == "user":
                Color(0.2, 0.5, 0.9, 1)
                self.rect = RoundedRectangle(radius=[10, 10, 0, 10], size=self.size, pos=self.pos)
            else:
                Color(0.85, 0.85, 0.85, 1)
                self.rect = RoundedRectangle(radius=[10, 10, 10, 0], size=self.size, pos=self.pos)
        self.bind(size=self.update_rect, pos=self.update_rect)

        self.text = f"{content}\n[size=10][color=#666666]{time}[/color][/size]"

        self.register_event_type('on_long_touch')
        self.last_touch_down = None

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.last_touch_down = touch.time
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.last_touch_down:
            if touch.time - self.last_touch_down > 0.5:
                self.dispatch('on_long_touch')
            self.last_touch_down = None
            return True
        return super().on_touch_up(touch)

    def on_long_touch(self):
        clipboard.copy(self.content)
        popup = Popup(title="提示", content=Label(text="已复制消息内容"), size_hint=(0.6, 0.3))
        popup.open()
        asyncio.run_coroutine_threadsafe(self.close_popup(popup), asyncio.get_event_loop())

    async def close_popup(self, popup):
        await asyncio.sleep(2)
        popup.dismiss()

# 主聊天界面（核心优化）
class GrokChatApp(App):
    def build(self):
        init_default_data(self)
        self.session_manager = SessionManager()
        self.api_key = get_api_key()
        self.api_url = get_api_url()  # 新增：读取自定义API地址

        # 检查API密钥，无则弹出输入框
        if not self.api_key:
            self.show_api_key_popup()

        # 主布局（无修改）
        main_layout = BoxLayout(orientation="horizontal", spacing=5, padding=5)

        # 左侧：会话列表
        self.session_list_layout = BoxLayout(orientation="vertical", size_hint=(0.3, 1))
        session_title = Label(text="会话列表", size_hint=(1, 0.05), font_size=16, bold=True)
        self.session_list_layout.add_widget(session_title)
        self.session_scroll = ScrollView(size_hint=(1, 0.9))
        self.session_grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.session_grid.bind(minimum_height=self.session_grid.setter('height'))
        self.session_scroll.add_widget(self.session_grid)
        self.session_list_layout.add_widget(self.session_scroll)
        new_session_btn = Button(text="+ 新建会话", size_hint=(1, 0.05), background_color=(0.2, 0.5, 0.9, 1))
        new_session_btn.bind(on_press=self.create_new_session)
        self.session_list_layout.add_widget(new_session_btn)
        main_layout.add_widget(self.session_list_layout)

        # 右侧：聊天界面
        self.chat_layout = BoxLayout(orientation="vertical", size_hint=(0.7, 1))
        self.chat_title = Label(text=self.session_manager.get_current_session()["name"], 
                                size_hint=(1, 0.05), font_size=16, bold=True)
        self.chat_layout.add_widget(self.chat_title)
        self.chat_scroll = ScrollView(size_hint=(1, 0.85))
        self.chat_messages = GridLayout(cols=1, spacing=10, size_hint_y=None, padding=[10, 10, 10, 10])
        self.chat_messages.bind(minimum_height=self.chat_messages.setter('height'))
        self.chat_scroll.add_widget(self.chat_messages)
        self.chat_layout.add_widget(self.chat_scroll)
        input_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.1), spacing=5)
        self.msg_input = TextInput(hint_text="输入消息...", size_hint=(0.85, 1), multiline=True)
        send_btn = Button(text="发送", size_hint=(0.15, 1), background_color=(0.2, 0.5, 0.9, 1))
        send_btn.bind(on_press=self.send_message)
        input_layout.add_widget(self.msg_input)
        input_layout.add_widget(send_btn)
        self.chat_layout.add_widget(input_layout)
        main_layout.add_widget(self.chat_layout)

        self.load_session_list()
        self.load_chat_messages()

        return main_layout

    # ========== 优化1：修改API密钥弹窗（新增自定义API地址） ==========
    def show_api_key_popup(self):
        popup_layout = BoxLayout(orientation="vertical", spacing=10, padding=20)
        # 1. API密钥输入
        popup_layout.add_widget(Label(text="请输入Grok API密钥（需X Premium+权限）"))
        self.api_key_input = TextInput(multiline=False)
        popup_layout.add_widget(self.api_key_input)
        
        # 2. 新增：自定义API地址（高级选项，默认填充官方地址）
        popup_layout.add_widget(Label(text="自定义API地址（可选）", font_size=12, color=(0.6, 0.6, 0.6, 1)))
        self.api_url_input = TextInput(multiline=False, text=self.api_url)
        popup_layout.add_widget(self.api_url_input)
        
        # 3. 提示文案（解决地域限制困惑）
        tip_label = Label(text="提示：官方API仅限部分地区/X Premium+用户访问，如无法使用可修改API地址", 
                          font_size=10, color=(0.8, 0.4, 0.4, 1), size_hint=(1, 0.2))
        popup_layout.add_widget(tip_label)
        
        # 4. 确认按钮
        confirm_btn = Button(text="确认")
        confirm_btn.bind(on_press=self.save_api_config)  # 改为保存密钥+地址
        popup_layout.add_widget(confirm_btn)

        self.api_popup = Popup(title="API配置", content=popup_layout, size_hint=(0.8, 0.7), auto_dismiss=False)
        self.api_popup.open()

    # ========== 优化1：新增保存API配置（密钥+地址） ==========
    def save_api_config(self, instance):
        api_key = self.api_key_input.text.strip()
        api_url = self.api_url_input.text.strip()
        
        # 验证密钥
        if not api_key:
            popup = Popup(title="错误", content=Label(text="API密钥不能为空！"), size_hint=(0.6, 0.3))
            popup.open()
            return
        if len(api_key) < 10:
            popup = Popup(title="错误", content=Label(text="API密钥格式错误！"), size_hint=(0.6, 0.3))
            popup.open()
            return
        
        # 验证API地址（简单格式检查）
        if not api_url.startswith("http"):
            popup = Popup(title="提示", content=Label(text="API地址需以http/https开头"), size_hint=(0.6, 0.3))
            popup.open()
            return
        
        # 保存密钥和地址
        save_api_key(api_key)
        save_api_url(api_url)
        self.api_key = api_key
        self.api_url = api_url
        self.api_popup.dismiss()

    # 会话管理相关函数（无修改）
    def load_session_list(self):
        self.session_grid.clear_widgets()
        for session in self.session_manager.sessions:
            session_item = BoxLayout(orientation="vertical", size_hint_y=None, height=80, padding=5)
            session_name = Label(text=session["name"], font_size=14, bold=True, size_hint=(1, 0.5))
            preview = Label(text=f"{session['last_msg']} | {session['timestamp']}", 
                            font_size=12, color=(0.6, 0.6, 0.6, 1), size_hint=(1, 0.3))
            btn_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.2), spacing=5)
            rename_btn = Button(text="重命名", size_hint=(0.5, 1), font_size=10, background_color=(0.7, 0.7, 0.7, 1))
            rename_btn.bind(on_press=lambda x, s=session["id"]: self.rename_session(s))
            delete_btn = Button(text="删除", size_hint=(0.5, 1), font_size=10, background_color=(0.9, 0.3, 0.3, 1))
            delete_btn.bind(on_press=lambda x, s=session["id"]: self.delete_session(s))
            btn_layout.add_widget(rename_btn)
            btn_layout.add_widget(delete_btn)

            session_item.add_widget(session_name)
            session_item.add_widget(preview)
            session_item.add_widget(btn_layout)
            session_item.bind(on_touch_down=lambda x, y, s=session["id"]: self.switch_session(s) if x.collide_point(*y.pos) else None)
            if session["id"] == self.session_manager.current_session_id:
                with session_item.canvas.before:
                    Color(0.9, 0.9, 0.9, 1)
                    RoundedRectangle(size=session_item.size, pos=session_item.pos, radius=[5])
            self.session_grid.add_widget(session_item)

    def create_new_session(self, instance):
        session_id = self.session_manager.create_session()
        self.switch_session(session_id)
        self.load_session_list()
        self.clear_chat_messages()
        self.chat_title.text = self.session_manager.get_current_session()["name"]

    def rename_session(self, session_id):
        popup_layout = BoxLayout(orientation="vertical", spacing=10, padding=20)
        popup_layout.add_widget(Label(text="输入新的会话名称"))
        rename_input = TextInput(multiline=False, text=self.session_manager.get_current_session()["name"])
        popup_layout.add_widget(rename_input)
        confirm_btn = Button(text="确认")
        confirm_btn.bind(on_press=lambda x: self.confirm_rename(session_id, rename_input.text))
        popup_layout.add_widget(confirm_btn)
        self.rename_popup = Popup(title="重命名会话", content=popup_layout, size_hint=(0.8, 0.5), auto_dismiss=False)
        self.rename_popup.open()

    def confirm_rename(self, session_id, new_name):
        if not new_name.strip():
            popup = Popup(title="错误", content=Label(text="会话名称不能为空！"), size_hint=(0.6, 0.3))
            popup.open()
            return
        self.session_manager.rename_session(session_id, new_name.strip())
        self.rename_popup.dismiss()
        self.load_session_list()
        if session_id == self.session_manager.current_session_id:
            self.chat_title.text = new_name.strip()

    def delete_session(self, session_id):
        success = self.session_manager.delete_session(session_id)
        if not success:
            popup = Popup(title="提示", content=Label(text="默认会话不能删除！"), size_hint=(0.6, 0.3))
            popup.open()
            return
        self.load_session_list()
        self.load_chat_messages()
        self.chat_title.text = self.session_manager.get_current_session()["name"]

    def switch_session(self, session_id):
        self.session_manager.current_session_id = session_id
        self.session_manager.save_sessions()
        self.load_session_list()
        self.load_chat_messages()
        self.chat_title.text = self.session_manager.get_current_session()["name"]

    def load_chat_messages(self):
        self.clear_chat_messages()
        current_session = self.session_manager.get_current_session()
        for msg in current_session["messages"]:
            self.add_message_bubble(msg["content"], msg["role"], msg["time"])
        self.chat_scroll.scroll_y = 0

    def clear_chat_messages(self):
        self.chat_messages.clear_widgets()

    def add_message_bubble(self, content, role, time):
        bubble = MessageBubble(content, role, time, size_hint_x=None, width=WINDOW_WIDTH*0.5)
        if role == "user":
            bubble.halign = "right"
            bubble.pos_hint = {"right": 1}
        else:
            bubble.halign = "left"
            bubble.pos_hint = {"left": 0}
        self.chat_messages.add_widget(bubble)

    def send_message(self, instance):
        user_msg = self.msg_input.text.strip()
        if not user_msg:
            return
        if not self.api_key:
            self.show_api_key_popup()
            return

        self.msg_input.text = ""

        current_session = self.session_manager.get_current_session()
        if len(current_session["messages"]) == 0 and current_session["id"] != "default":
            self.session_manager.rename_session(current_session["id"], user_msg[:20])
            self.chat_title.text = user_msg[:20]
            self.load_session_list()

        current_time = datetime.datetime.now().strftime("%H:%M")
        self.add_message_bubble(user_msg, "user", current_time)
        self.chat_scroll.scroll_y = 0

        asyncio.run_coroutine_threadsafe(self.get_grok_response(user_msg), asyncio.get_event_loop())

    # ========== 优化2：流式请求（分类异常处理） ==========
    async def get_grok_response(self, user_msg):
        current_session = self.session_manager.get_current_session()
        # 使用自定义API地址
        grok_api_url = self.api_url

        messages = current_session["context"] + [{"role": "user", "content": user_msg}]
        payload = {
            "model": "grok-1",
            "messages": messages,
            "stream": True
        }

        grok_bubble = MessageBubble("", "grok", datetime.datetime.now().strftime("%H:%M"), 
                                    size_hint_x=None, width=WINDOW_WIDTH*0.5)
        grok_bubble.halign = "left"
        grok_bubble.pos_hint = {"left": 0}
        self.chat_messages.add_widget(grok_bubble)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    grok_api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)  # 新增超时设置
                ) as response:
                    # 状态码异常处理
                    if response.status == 401:
                        self.update_bubble_text(grok_bubble, "API密钥无效或无访问权限（需X Premium+）")
                        return
                    elif response.status == 403:
                        self.update_bubble_text(grok_bubble, "当前地区不支持访问该API")
                        return
                    elif response.status == 429:
                        self.update_bubble_text(grok_bubble, "请求过于频繁，请稍后重试")
                        return
                    elif response.status != 200:
                        self.update_bubble_text(grok_bubble, f"请求失败：{response.status}（请检查API地址）")
                        return

                    # 流式读取响应
                    full_response = ""
                    async for line in response.content:
                        if line:
                            line_text = line.decode('utf-8').strip()
                            if line_text.startswith("data: "):
                                data = line_text[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    json_data = json.loads(data)
                                    delta = json_data["choices"][0]["delta"]
                                    if "content" in delta:
                                        full_response += delta["content"]
                                        self.update_bubble_text(grok_bubble, full_response)
                                        self.chat_scroll.scroll_y = 0
                                except Exception as e:
                                    continue

            self.session_manager.update_session_msg(current_session["id"], user_msg, full_response)
            self.load_session_list()

        # ========== 优化2：分类异常提示 ==========
        except aiohttp.ClientConnectorError:
            self.update_bubble_text(grok_bubble, "无法连接服务器，请检查网络或API地址")
        except asyncio.TimeoutError:
            self.update_bubble_text(grok_bubble, "请求超时，请检查网络或稍后重试")
        except aiohttp.ClientError as e:
            self.update_bubble_text(grok_bubble, f"网络请求错误：{type(e).__name__}")
        except Exception as e:
            self.update_bubble_text(grok_bubble, f"未知错误：{type(e).__name__}（请检查API配置）")

    @mainthread
    def update_bubble_text(self, bubble, text):
        bubble.text = f"{text}\n[size=10][color=#666666]{bubble.time}[/color][/size]"
        bubble.content = text

if __name__ == "__main__":
    Window.softinput_mode = "below_target"
    GrokChatApp().run()