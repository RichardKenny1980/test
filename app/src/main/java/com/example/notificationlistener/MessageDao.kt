package com.example.notificationlistener

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query

@Dao
interface MessageDao {

    @Insert
    suspend fun insert(message: Message)

    @Query("SELECT * FROM messages ORDER BY id DESC")
    fun getAllMessages(): List<Message>
}
