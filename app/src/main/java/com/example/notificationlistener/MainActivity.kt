package com.example.notificationlistener

import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var recyclerView: RecyclerView
    private lateinit var messageAdapter: MessageAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        recyclerView = findViewById(R.id.recyclerView)
        recyclerView.layoutManager = LinearLayoutManager(this)

        val database = MessageDatabase.getDatabase(application)
        val messageDao = database.messageDao()

        GlobalScope.launch {
            val messages = messageDao.getAllMessages()
            withContext(Dispatchers.Main) {
                messageAdapter = MessageAdapter(messages)
                recyclerView.adapter = messageAdapter
            }
        }
    }
}
