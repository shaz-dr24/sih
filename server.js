import express from "express";
import cors from "cors";
import { MongoClient } from "mongodb";
import dashboardRoute from "./routes/dashboard.js";

const app = express();
app.use(cors());
app.use(express.json());

// --------------------
// MongoDB Connection
// --------------------
const MONGO_URL = "mongodb+srv://sara:6pathiyam@cluster0.l1g9jjw.mongodb.net/?appName=Cluster0";
const DB_NAME = "n8n1";
const COLLECTION_NAME = "n8n_chat_histories";

let collection;

async function connectDB() {
  try {
    const client = new MongoClient(MONGO_URL);
    await client.connect();
    console.log("✅ MongoDB Connected");

    const db = client.db(DB_NAME);
    collection = db.collection(COLLECTION_NAME);

    app.use("/api/dashboard", dashboardRoute(collection));

    app.listen(5000, () => {
      console.log("🚀 Server running on port 5000");
    });

  } catch (err) {
    console.error("❌ MongoDB Connection Error:", err);
  }
}

connectDB();