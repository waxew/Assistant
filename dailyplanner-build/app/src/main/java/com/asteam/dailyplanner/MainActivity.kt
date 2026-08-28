package com.asteam.dailyplanner

import android.app.Activity
import android.app.AlertDialog
import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : Activity() {
    private lateinit var db: PlannerDb
    private lateinit var taskList: LinearLayout
    private lateinit var progressText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(245, 246, 250)
        db = PlannerDb()
        setContentView(buildUi())
        refreshTasks()
    }

    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(18))
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            setBackgroundColor(Color.rgb(245, 246, 250))
        }

        root.addView(TextView(this).apply {
            text = "برنامه‌ریز روزانه"
            textSize = 27f
            setTextColor(Color.rgb(35, 39, 47))
            setTypeface(typeface, 1)
        })

        root.addView(TextView(this).apply {
            text = SimpleDateFormat("EEEE، d MMMM", Locale("fa")).format(Date())
            textSize = 14f
            setTextColor(Color.DKGRAY)
            setPadding(0, dp(4), 0, dp(16))
        })

        progressText = TextView(this).apply {
            textSize = 16f
            setTextColor(Color.rgb(72, 82, 96))
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = rounded(Color.WHITE, 20f)
        }
        root.addView(progressText, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(12) })

        val add = Button(this).apply {
            text = "+ افزودن کار جدید"
            textSize = 16f
            setOnClickListener { showAddDialog() }
        }
        root.addView(add, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(12) })

        val scroll = ScrollView(this)
        taskList = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(taskList)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        return root
    }

    private fun showAddDialog() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), 0)
        }
        val title = EditText(this).apply { hint = "عنوان کار" }
        val note = EditText(this).apply { hint = "یادداشت (اختیاری)" }
        box.addView(title)
        box.addView(note)
        AlertDialog.Builder(this)
            .setTitle("کار جدید")
            .setView(box)
            .setPositiveButton("ذخیره") { _, _ ->
                val t = title.text.toString().trim()
                if (t.isNotEmpty()) {
                    db.addTask(t, note.text.toString().trim())
                    refreshTasks()
                }
            }
            .setNegativeButton("انصراف", null)
            .show()
    }

    private fun refreshTasks() {
        taskList.removeAllViews()
        val tasks = db.allTasks()
        val done = tasks.count { it.done }
        progressText.text = if (tasks.isEmpty()) "هنوز کاری ثبت نشده است" else "پیشرفت امروز: $done از ${tasks.size} کار انجام شده"
        if (tasks.isEmpty()) {
            taskList.addView(TextView(this).apply {
                text = "برای شروع، اولین کار روزانه‌ات را اضافه کن."
                gravity = Gravity.CENTER
                setPadding(0, dp(48), 0, 0)
                setTextColor(Color.GRAY)
            })
            return
        }
        tasks.forEach { task -> taskList.addView(taskCard(task)) }
    }

    private fun taskCard(task: Task): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = rounded(Color.WHITE, 18f)
        }
        val check = CheckBox(this).apply {
            isChecked = task.done
            setOnCheckedChangeListener { _, value -> db.setDone(task.id, value); refreshTasks() }
        }
        val textBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        textBox.addView(TextView(this).apply {
            text = task.title
            textSize = 17f
            setTextColor(Color.rgb(35, 39, 47))
            setTypeface(typeface, 1)
        })
        if (task.note.isNotBlank()) textBox.addView(TextView(this).apply {
            text = task.note
            textSize = 13f
            setTextColor(Color.GRAY)
        })
        val del = Button(this).apply {
            text = "حذف"
            setOnClickListener { db.deleteTask(task.id); refreshTasks() }
        }
        row.addView(check)
        row.addView(textBox, LinearLayout.LayoutParams(0, -2, 1f))
        row.addView(del)
        return FrameLayout(this).apply {
            setPadding(0, 0, 0, dp(10))
            addView(row, FrameLayout.LayoutParams(-1, -2))
        }
    }

    private fun rounded(color: Int, radius: Float) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius.toInt()).toFloat()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    data class Task(val id: Long, val title: String, val note: String, val done: Boolean)

    inner class PlannerDb : SQLiteOpenHelper(this@MainActivity, "daily_planner.db", null, 1) {
        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL("CREATE TABLE tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',done INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)")
        }
        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}
        fun addTask(title: String, note: String) = writableDatabase.insert("tasks", null, ContentValues().apply {
            put("title", title); put("note", note); put("done", 0); put("created_at", System.currentTimeMillis())
        })
        fun setDone(id: Long, done: Boolean) = writableDatabase.update("tasks", ContentValues().apply { put("done", if (done) 1 else 0) }, "id=?", arrayOf(id.toString()))
        fun deleteTask(id: Long) = writableDatabase.delete("tasks", "id=?", arrayOf(id.toString()))
        fun allTasks(): List<Task> {
            val out = mutableListOf<Task>()
            readableDatabase.rawQuery("SELECT id,title,note,done FROM tasks ORDER BY done ASC, created_at DESC", null).use { c ->
                while (c.moveToNext()) out += Task(c.getLong(0), c.getString(1), c.getString(2), c.getInt(3) == 1)
            }
            return out
        }
    }
}
