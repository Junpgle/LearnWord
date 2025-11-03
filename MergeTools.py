import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os


class FileMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("代码文件合并工具")
        self.root.geometry("700x500")

        # 设置中文字体
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))

        # 选择的文件列表
        self.selected_files = []

        # 创建UI组件
        self.create_widgets()

    def create_widgets(self):
        # 标题
        title_label = ttk.Label(
            self.root,
            text="代码文件合并工具 - 合并格式: 文件名+内容",
            font=("SimHei", 12, "bold")
        )
        title_label.pack(pady=10)

        # 按钮区域
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        select_btn = ttk.Button(
            button_frame,
            text="选择文件",
            command=self.select_files
        )
        select_btn.grid(row=0, column=0, padx=5)

        remove_btn = ttk.Button(
            button_frame,
            text="移除选中",
            command=self.remove_selected
        )
        remove_btn.grid(row=0, column=1, padx=5)

        clear_btn = ttk.Button(
            button_frame,
            text="清空列表",
            command=self.clear_list
        )
        clear_btn.grid(row=0, column=2, padx=5)

        merge_btn = ttk.Button(
            button_frame,
            text="合并文件",
            command=self.merge_files
        )
        merge_btn.grid(row=0, column=3, padx=5)

        # 文件列表区域
        list_frame = ttk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ttk.Label(list_frame, text="已选择文件:").pack(anchor=tk.W)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 文件列表
        self.file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.EXTENDED,
            font=("SimHei", 10)
        )
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # 状态区域
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def select_files(self):
        """选择多个文件"""
        file_types = [
            ("所有文件", "*.*"),
            ("Python文件", "*.py"),
            ("文本文件", "*.txt"),
            ("JavaScript", "*.js"),
            ("HTML", "*.html"),
            ("CSS", "*.css"),
            ("Java", "*.java"),
            ("C/C++", "*.c;*.cpp;*.h")
        ]

        files = filedialog.askopenfilenames(
            title="选择要合并的文件",
            filetypes=file_types
        )

        if files:
            # 避免重复添加
            new_files = [f for f in files if f not in self.selected_files]
            self.selected_files.extend(new_files)

            # 更新列表显示
            for file in new_files:
                self.file_listbox.insert(tk.END, os.path.basename(file))

            self.status_var.set(f"已添加 {len(new_files)} 个文件，共 {len(self.selected_files)} 个")

    def remove_selected(self):
        """移除选中的文件"""
        selected_indices = sorted(self.file_listbox.curselection(), reverse=True)
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择要移除的文件")
            return

        # 从列表中移除
        for index in selected_indices:
            del self.selected_files[index]
            self.file_listbox.delete(index)

        self.status_var.set(f"已移除 {len(selected_indices)} 个文件，剩余 {len(self.selected_files)} 个")

    def clear_list(self):
        """清空文件列表"""
        if messagebox.askyesno("确认", "确定要清空所有文件吗？"):
            self.selected_files.clear()
            self.file_listbox.delete(0, tk.END)
            self.status_var.set("已清空文件列表")

    def merge_files(self):
        """合并选中的文件"""
        if not self.selected_files:
            messagebox.showinfo("提示", "请先选择要合并的文件")
            return

        # 选择保存位置
        output_file = filedialog.asksaveasfilename(
            title="保存合并文件",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if not output_file:
            return

        try:
            with open(output_file, 'w', encoding='utf-8') as out_f:
                for file_path in self.selected_files:
                    file_name = os.path.basename(file_path)

                    # 写入文件名
                    out_f.write(f"===== {file_name} =====\n\n")

                    # 写入文件内容
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as in_f:
                        content = in_f.read()
                        out_f.write(content)

                    # 每个文件之间添加分隔线
                    out_f.write("\n\n" + "=" * 50 + "\n\n")

            self.status_var.set(f"文件合并成功！已保存至: {output_file}")
            messagebox.showinfo("成功", f"文件已成功合并并保存至:\n{output_file}")

        except Exception as e:
            error_msg = f"合并文件时出错: {str(e)}"
            self.status_var.set(error_msg)
            messagebox.showerror("错误", error_msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = FileMergerApp(root)
    root.mainloop()