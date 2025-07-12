const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const cron = require('node-cron');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const PayPal = require('paypal-rest-sdk');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use(limiter);

// MongoDB connection
mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/watchearn', {
  useNewUrlParser: true,
  useUnifiedTopology: true
});

// PayPal configuration
PayPal.configure({
  mode: process.env.PAYPAL_MODE || 'sandbox',
  client_id: process.env.PAYPAL_CLIENT_ID,
  client_secret: process.env.PAYPAL_CLIENT_SECRET
});

// User Schema
const userSchema = new mongoose.Schema({
  username: { type: String, required: true, unique: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  phone: { type: String },
  balance: { type: Number, default: 0 },
  totalEarned: { type: Number, default: 0 },
  watchTime: { type: Number, default: 0 }, // in seconds
  isActive: { type: Boolean, default: true },
  referralCode: { type: String, unique: true },
  referredBy: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
  paymentMethods: [{
    type: { type: String, enum: ['paypal', 'mpesa'] },
    details: { type: mongoose.Schema.Types.Mixed }
  }],
  createdAt: { type: Date, default: Date.now },
  lastActive: { type: Date, default: Date.now }
});

// Video Schema
const videoSchema = new mongoose.Schema({
  title: { type: String, required: true },
  description: { type: String },
  filename: { type: String, required: true },
  originalName: { type: String, required: true },
  mimetype: { type: String, required: true },
  size: { type: Number, required: true },
  duration: { type: Number }, // in seconds
  views: { type: Number, default: 0 },
  likes: { type: Number, default: 0 },
  dislikes: { type: Number, default: 0 },
  category: { type: String, required: true },
  tags: [String],
  uploadedBy: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
  isActive: { type: Boolean, default: true },
  monetization: {
    earningsPerSecond: { type: Number, default: 0.001 }, // Owner earnings per second
    userEarningsPerSecond: { type: Number, default: 0.0001 } // User earnings per second
  },
  createdAt: { type: Date, default: Date.now }
});

// Watch Session Schema
const watchSessionSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  video: { type: mongoose.Schema.Types.ObjectId, ref: 'Video', required: true },
  startTime: { type: Date, default: Date.now },
  endTime: { type: Date },
  duration: { type: Number, default: 0 }, // in seconds
  userEarnings: { type: Number, default: 0 },
  ownerEarnings: { type: Number, default: 0 },
  isActive: { type: Boolean, default: true }
});

// Transaction Schema
const transactionSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  type: { type: String, enum: ['earning', 'withdrawal', 'referral_bonus'], required: true },
  amount: { type: Number, required: true },
  description: { type: String },
  status: { type: String, enum: ['pending', 'completed', 'failed'], default: 'pending' },
  paymentMethod: { type: String, enum: ['paypal', 'mpesa'] },
  externalTransactionId: { type: String },
  createdAt: { type: Date, default: Date.now }
});

// Withdrawal Schema
const withdrawalSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  amount: { type: Number, required: true },
  method: { type: String, enum: ['paypal', 'mpesa'], required: true },
  details: { type: mongoose.Schema.Types.Mixed },
  status: { type: String, enum: ['pending', 'processing', 'completed', 'failed'], default: 'pending' },
  transactionId: { type: String },
  createdAt: { type: Date, default: Date.now },
  processedAt: { type: Date }
});

// Models
const User = mongoose.model('User', userSchema);
const Video = mongoose.model('Video', videoSchema);
const WatchSession = mongoose.model('WatchSession', watchSessionSchema);
const Transaction = mongoose.model('Transaction', transactionSchema);
const Withdrawal = mongoose.model('Withdrawal', withdrawalSchema);

// JWT middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }

  jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key', (err, user) => {
    if (err) return res.status(403).json({ error: 'Invalid token' });
    req.user = user;
    next();
  });
};

// File upload configuration
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = 'uploads/videos';
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, uniqueSuffix + path.extname(file.originalname));
  }
});

const upload = multer({
  storage: storage,
  limits: {
    fileSize: 500 * 1024 * 1024, // 500MB limit
  },
  fileFilter: (req, file, cb) => {
    const allowedTypes = ['video/mp4', 'video/avi', 'video/mkv', 'video/mov'];
    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type. Only video files are allowed.'));
    }
  }
});

// Helper function to generate referral code
const generateReferralCode = () => {
  return Math.random().toString(36).substring(2, 8).toUpperCase();
};

// Helper function for M-Pesa payment
const processMpesaPayment = async (phoneNumber, amount) => {
  try {
    const response = await axios.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest', {
      BusinessShortCode: process.env.MPESA_SHORTCODE,
      Password: process.env.MPESA_PASSWORD,
      Timestamp: new Date().toISOString().replace(/[-:]/g, '').slice(0, 14),
      TransactionType: 'CustomerPayBillOnline',
      Amount: amount,
      PartyA: phoneNumber,
      PartyB: process.env.MPESA_SHORTCODE,
      PhoneNumber: phoneNumber,
      CallBackURL: process.env.MPESA_CALLBACK_URL,
      AccountReference: 'WatchEarn',
      TransactionDesc: 'Payment for WatchEarn'
    }, {
      headers: {
        'Authorization': `Bearer ${process.env.MPESA_ACCESS_TOKEN}`,
        'Content-Type': 'application/json'
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('M-Pesa payment error:', error);
    throw error;
  }
};

// Routes

// User Registration
app.post('/api/register', async (req, res) => {
  try {
    const { username, email, password, phone, referralCode } = req.body;
    
    // Check if user already exists
    const existingUser = await User.findOne({ 
      $or: [{ email }, { username }] 
    });
    
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists' });
    }
    
    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Handle referral
    let referredBy = null;
    if (referralCode) {
      referredBy = await User.findOne({ referralCode });
    }
    
    // Create user
    const user = new User({
      username,
      email,
      password: hashedPassword,
      phone,
      referralCode: generateReferralCode(),
      referredBy: referredBy ? referredBy._id : null
    });
    
    await user.save();
    
    // Give referral bonus
    if (referredBy) {
      referredBy.balance += 1.0; // $1 referral bonus
      await referredBy.save();
      
      // Record referral transaction
      const transaction = new Transaction({
        user: referredBy._id,
        type: 'referral_bonus',
        amount: 1.0,
        description: `Referral bonus for ${username}`,
        status: 'completed'
      });
      await transaction.save();
    }
    
    // Generate JWT token
    const token = jwt.sign(
      { userId: user._id, username: user.username },
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '7d' }
    );
    
    res.status(201).json({
      message: 'User registered successfully',
      token,
      user: {
        id: user._id,
        username: user.username,
        email: user.email,
        balance: user.balance,
        referralCode: user.referralCode
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// User Login
app.post('/api/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Find user
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(400).json({ error: 'Invalid credentials' });
    }
    
    // Check password
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(400).json({ error: 'Invalid credentials' });
    }
    
    // Update last active
    user.lastActive = new Date();
    await user.save();
    
    // Generate JWT token
    const token = jwt.sign(
      { userId: user._id, username: user.username },
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '7d' }
    );
    
    res.json({
      message: 'Login successful',
      token,
      user: {
        id: user._id,
        username: user.username,
        email: user.email,
        balance: user.balance,
        totalEarned: user.totalEarned,
        watchTime: user.watchTime,
        referralCode: user.referralCode
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get User Profile
app.get('/api/profile', authenticateToken, async (req, res) => {
  try {
    const user = await User.findById(req.user.userId).select('-password');
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Upload Video
app.post('/api/videos/upload', authenticateToken, upload.single('video'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No video file provided' });
    }
    
    const { title, description, category, tags } = req.body;
    
    const video = new Video({
      title,
      description,
      filename: req.file.filename,
      originalName: req.file.originalname,
      mimetype: req.file.mimetype,
      size: req.file.size,
      category,
      tags: tags ? tags.split(',').map(tag => tag.trim()) : [],
      uploadedBy: req.user.userId
    });
    
    await video.save();
    
    res.status(201).json({
      message: 'Video uploaded successfully',
      video: {
        id: video._id,
        title: video.title,
        filename: video.filename,
        category: video.category,
        createdAt: video.createdAt
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get All Videos
app.get('/api/videos', async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 20;
    const category = req.query.category;
    const search = req.query.search;
    
    let query = { isActive: true };
    
    if (category) {
      query.category = category;
    }
    
    if (search) {
      query.$or = [
        { title: { $regex: search, $options: 'i' } },
        { description: { $regex: search, $options: 'i' } },
        { tags: { $in: [new RegExp(search, 'i')] } }
      ];
    }
    
    const videos = await Video.find(query)
      .populate('uploadedBy', 'username')
      .sort({ createdAt: -1 })
      .skip((page - 1) * limit)
      .limit(limit);
    
    const totalVideos = await Video.countDocuments(query);
    
    res.json({
      videos,
      pagination: {
        currentPage: page,
        totalPages: Math.ceil(totalVideos / limit),
        totalVideos,
        hasNext: page < Math.ceil(totalVideos / limit),
        hasPrev: page > 1
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Stream Video
app.get('/api/videos/:id/stream', async (req, res) => {
  try {
    const video = await Video.findById(req.params.id);
    if (!video) {
      return res.status(404).json({ error: 'Video not found' });
    }
    
    const videoPath = path.join(__dirname, 'uploads', 'videos', video.filename);
    
    if (!fs.existsSync(videoPath)) {
      return res.status(404).json({ error: 'Video file not found' });
    }
    
    const stat = fs.statSync(videoPath);
    const fileSize = stat.size;
    const range = req.headers.range;
    
    if (range) {
      const parts = range.replace(/bytes=/, "").split("-");
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunksize = (end - start) + 1;
      const file = fs.createReadStream(videoPath, { start, end });
      const head = {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunksize,
        'Content-Type': 'video/mp4',
      };
      res.writeHead(206, head);
      file.pipe(res);
    } else {
      const head = {
        'Content-Length': fileSize,
        'Content-Type': 'video/mp4',
      };
      res.writeHead(200, head);
      fs.createReadStream(videoPath).pipe(res);
    }
    
    // Increment views
    video.views += 1;
    await video.save();
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Start Watch Session
app.post('/api/watch/start', authenticateToken, async (req, res) => {
  try {
    const { videoId } = req.body;
    
    const video = await Video.findById(videoId);
    if (!video) {
      return res.status(404).json({ error: 'Video not found' });
    }
    
    // Check if user has an active session for this video
    const existingSession = await WatchSession.findOne({
      user: req.user.userId,
      video: videoId,
      isActive: true
    });
    
    if (existingSession) {
      return res.json({ sessionId: existingSession._id });
    }
    
    // Create new watch session
    const watchSession = new WatchSession({
      user: req.user.userId,
      video: videoId
    });
    
    await watchSession.save();
    
    res.json({ sessionId: watchSession._id });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update Watch Session (called every second)
app.post('/api/watch/update', authenticateToken, async (req, res) => {
  try {
    const { sessionId, secondsWatched } = req.body;
    
    const session = await WatchSession.findById(sessionId)
      .populate('video')
      .populate('user');
    
    if (!session || !session.isActive) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    // Update session duration
    session.duration = secondsWatched;
    
    // Calculate earnings
    const userEarningsPerSecond = session.video.monetization.userEarningsPerSecond;
    const ownerEarningsPerSecond = session.video.monetization.earningsPerSecond;
    
    const newUserEarnings = userEarningsPerSecond;
    const newOwnerEarnings = ownerEarningsPerSecond;
    
    session.userEarnings += newUserEarnings;
    session.ownerEarnings += newOwnerEarnings;
    
    await session.save();
    
    // Update user balance and stats
    const user = await User.findById(req.user.userId);
    user.balance += newUserEarnings;
    user.totalEarned += newUserEarnings;
    user.watchTime += 1;
    user.lastActive = new Date();
    await user.save();
    
    // Create earning transaction
    const transaction = new Transaction({
      user: req.user.userId,
      type: 'earning',
      amount: newUserEarnings,
      description: `Watched ${session.video.title}`,
      status: 'completed'
    });
    await transaction.save();
    
    res.json({
      userEarnings: newUserEarnings,
      totalEarnings: session.userEarnings,
      balance: user.balance
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// End Watch Session
app.post('/api/watch/end', authenticateToken, async (req, res) => {
  try {
    const { sessionId } = req.body;
    
    const session = await WatchSession.findById(sessionId);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    session.isActive = false;
    session.endTime = new Date();
    await session.save();
    
    res.json({ message: 'Session ended successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get User Transactions
app.get('/api/transactions', authenticateToken, async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 20;
    
    const transactions = await Transaction.find({ user: req.user.userId })
      .sort({ createdAt: -1 })
      .skip((page - 1) * limit)
      .limit(limit);
    
    const totalTransactions = await Transaction.countDocuments({ user: req.user.userId });
    
    res.json({
      transactions,
      pagination: {
        currentPage: page,
        totalPages: Math.ceil(totalTransactions / limit),
        totalTransactions,
        hasNext: page < Math.ceil(totalTransactions / limit),
        hasPrev: page > 1
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Request Withdrawal
app.post('/api/withdraw', authenticateToken, async (req, res) => {
  try {
    const { amount, method, details } = req.body;
    
    const user = await User.findById(req.user.userId);
    
    if (amount > user.balance) {
      return res.status(400).json({ error: 'Insufficient balance' });
    }
    
    if (amount < 5) {
      return res.status(400).json({ error: 'Minimum withdrawal amount is $5' });
    }
    
    // Create withdrawal request
    const withdrawal = new Withdrawal({
      user: req.user.userId,
      amount,
      method,
      details,
      transactionId: uuidv4()
    });
    
    await withdrawal.save();
    
    // Deduct from user balance
    user.balance -= amount;
    await user.save();
    
    // Create transaction record
    const transaction = new Transaction({
      user: req.user.userId,
      type: 'withdrawal',
      amount: -amount,
      description: `Withdrawal via ${method}`,
      status: 'pending',
      paymentMethod: method
    });
    await transaction.save();
    
    res.json({
      message: 'Withdrawal request submitted',
      withdrawalId: withdrawal._id,
      transactionId: withdrawal.transactionId
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Process PayPal Withdrawal
app.post('/api/withdraw/paypal/process', authenticateToken, async (req, res) => {
  try {
    const { withdrawalId } = req.body;
    
    const withdrawal = await Withdrawal.findById(withdrawalId);
    if (!withdrawal) {
      return res.status(404).json({ error: 'Withdrawal not found' });
    }
    
    const payoutData = {
      sender_batch_header: {
        sender_batch_id: withdrawal.transactionId,
        email_subject: 'You have a payment'
      },
      items: [{
        recipient_type: 'EMAIL',
        amount: {
          value: withdrawal.amount.toString(),
          currency: 'USD'
        },
        receiver: withdrawal.details.email,
        note: 'Payment from WatchEarn App',
        sender_item_id: withdrawal._id.toString()
      }]
    };
    
    PayPal.payout.create(payoutData, (error, payout) => {
      if (error) {
        console.error('PayPal payout error:', error);
        withdrawal.status = 'failed';
        withdrawal.save();
        return res.status(500).json({ error: 'PayPal payout failed' });
      }
      
      withdrawal.status = 'completed';
      withdrawal.processedAt = new Date();
      withdrawal.save();
      
      res.json({ message: 'PayPal withdrawal processed successfully' });
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get Dashboard Stats (Owner)
app.get('/api/admin/stats', authenticateToken, async (req, res) => {
  try {
    const totalUsers = await User.countDocuments();
    const totalVideos = await Video.countDocuments();
    const totalWatchTime = await WatchSession.aggregate([
      { $group: { _id: null, totalTime: { $sum: '$duration' } } }
    ]);
    
    const totalEarnings = await WatchSession.aggregate([
      { $group: { _id: null, totalOwnerEarnings: { $sum: '$ownerEarnings' } } }
    ]);
    
    const dailyEarnings = await WatchSession.aggregate([
      {
        $match: {
          createdAt: { $gte: new Date(Date.now() - 24 * 60 * 60 * 1000) }
        }
      },
      { $group: { _id: null, dailyEarnings: { $sum: '$ownerEarnings' } } }
    ]);
    
    res.json({
      totalUsers,
      totalVideos,
      totalWatchTime: totalWatchTime[0]?.totalTime || 0,
      totalEarnings: totalEarnings[0]?.totalOwnerEarnings || 0,
      dailyEarnings: dailyEarnings[0]?.dailyEarnings || 0
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get Top Videos
app.get('/api/videos/top', async (req, res) => {
  try {
    const topVideos = await Video.find({ isActive: true })
      .sort({ views: -1 })
      .limit(10)
      .populate('uploadedBy', 'username');
    
    res.json(topVideos);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Real-time earnings calculation (runs every second)
cron.schedule('* * * * * *', async () => {
  try {
    const activeSessions = await WatchSession.find({ isActive: true })
      .populate('video')
      .populate('user');
    
    for (const session of activeSessions) {
      // Check if session is still active (user hasn't been inactive for too long)
      const lastUpdate = new Date(session.user.lastActive);
      const now = new Date();
      const timeDiff = (now - lastUpdate) / 1000; // seconds
      
      if (timeDiff > 30) { // If user inactive for more than 30 seconds, end session
        session.isActive = false;
        session.endTime = new Date();
        await session.save();
      }
    }
  } catch (error) {
    console.error('Cron job error:', error);
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({ error: 'File too large' });
    }
  }
  
  console.error('Error:', error);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log('Watch & Earn Backend API is ready!');
});

module.exports = app;
