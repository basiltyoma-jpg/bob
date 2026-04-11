import tkinter as tk
import sqlite3
import datetime

def get_statistic_data():
    all_data = []
    with sqlite3.connect('db/database.db') as db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        query = '''' SELECT * FROM payments JOIN expences
                     ON exspences.id = payments.expences_id '''
        cursor.execute(query)
        all_data = cursor
    return all_data
def get_common_item():
    data = get_statistic_data()
    quantity = {}
    for payments in data:
        if [payments['expences_id']] in quantity:
            quantity[payments['expences_id']]['qty'] += 1
        else:
            quantity[payments['expences_id']] = {'qty':1, 'name':payments['name']}
    return max(quantity.values(), key=lambda x:['qty'])['name']

root = tk.Tk()
root.title("winter")
#root.geometry("300x300")
#root.maxsize("700x700")
#root.minsize("200x200")
#root.resizable(width=False, height=False)

#frame_warp = tk.Frame(root)
frame_form = tk.Frame(root, bg="red")
frame_static = tk.Frame(root, bg="green")
frame_list = tk.Frame(root, bg="blue")

#frame_form.place(relx=0, rely=0, relwidth=0.5, relheight=0.5)
#frame_static.place(relx=0.5, rely=-0, relwidth=0.5, relheight=0.5)
#frame_list.place(relx=0, rely=0.5, relwidth=1, relheight=0.5)
#frame_warp.pack(fill="both")
#frame_form.pack(side="left", fill="both", expand=True, ipady=60)
#frame_static.pack(side="right", fill="both", expand=True, ipady=60)
#frame_list.pack(side="bottom", fill="both", expand=True)


frame_form.grid(row=0, column=0, sticky="ns")
frame_static.grid(row=0, column=1)
frame_list.grid(row=1, column=0, columnspan=2, sticky="we")

l_text = tk.Label(frame_static, text="Common item")
l_value = tk.Label(frame_static, get_common_item(), font="Helvetica 14 bold")
l_item_text = tk.Label(frame_static, text="expensive item")
l_item_value = tk.Label(frame_static, text="gift", font="Helvetica 14 bold")
l_day_text = tk.Label(frame_static, text="exspensive day")
l_day_value = tk.Label(frame_static, text="Friday", font="Helvetica 14 bold")
l_month_text = tk.Label(frame_static, text="expansive month")
l_month_value = tk.Label(frame_static, text="July", font="Helvetica 14 bold")

l_text.grid(row="0", column="0", sticky="w", padx=10, pady=10)
l_value.grid(row="0", column="1", sticky="e", padx=10, pady=10)
l_item_text.grid(row="1", column="0", sticky="w", padx=10, pady=10)
l_item_value.grid(row="1", column="1", sticky="e", padx=10, pady=10)
l_day_text.grid(row="2", column="0", sticky="w", padx=10, pady=10)
l_day_value.grid(row="2", column="1", sticky="e", padx=10, pady=10)
l_month_text.grid(row="3", column="0", sticky="w", padx=10, pady=10)
l_month_value.grid(row="3", column="1", sticky="e", padx=10, pady=10)

l_temp_form = tk.Label(frame_form, text="frame_form!")
l_temp_list = tk.Label(frame_list, text="frame_list!")
l_temp_form.pack(expand=True, padx=20, pady=20)
l_temp_list.pack(expand=True, padx=20, pady=20)

root.mainloop()

