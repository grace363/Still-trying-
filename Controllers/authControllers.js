```javascript
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { User, AppSettings } = require('../models');
const { generateReferralCode } = require('../utils/helpers');
const emailService = require('../services/emailService');

class AuthController {
  async register(req, res) {
    try {
      const { email, password, referralCode } = req.body;

      const existingUser = await User.findOne({ email });
      if (existingUser) {
        return res.status(400).json({ error: 'User already exists' });
      }

      const hashedPassword = await bcrypt.hash(password, 10);
      const verificationToken = jwt.sign({ email }, process.env.JWT_SECRET, { expiresIn: '24h' });

      const user = new User({
        email,
        password: hashedPassword,
        verificationToken,
        referralCode: generateReferralCode(),
        referredBy: referralCode
      });

      await user.save();
      await emailService.sendVerificationEmail(email, verificationToken);

      res.status(201).json({ 
        message: 'User registered successfully. Please check your email for verification.',
        referralCode: user.referralCode
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async login(req, res) {
    try {
      const { email, password } = req.body;

      const user = await User.findOne({ email });
      if (!user) {
        return res.status(400).json({ error: 'Invalid credentials' });
      }

      if (!user.isVerified) {
        return res.status(400).json({ error: 'Please verify your email first' });
      }

      const isPasswordValid = await bcrypt.compare(password, user.password);
      if (!isPasswordValid) {
        return res.status(400).json({ error: 'Invalid credentials' });
      }

      const token = jwt.sign({ userId: user._id }, process.env.JWT_SECRET, { expiresIn: '7d' });

      user.lastActivity = new Date();
      await user.save();

      res.json({
        token,
        user: {
          id: user._id,
          email: user.email,
          balance: user.balance,
          totalEarned: user.totalEarned,
          referralCode: user.referralCode
        }
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async verifyEmail(req, res) {
    try {
      const { token } = req.body;

      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      const user = await User.findOne({ email: decoded.email, verificationToken: token });

      if (!user) {
        return res.status(400).json({ error: 'Invalid verification token' });
      }

      user.isVerified = true;
      user.verificationToken = undefined;
      
      if (user.referredBy) {
        const referrer = await User.findOne({ referralCode: user.referredBy });
        if (referrer) {
          const settings = await AppSettings.findOne() || new AppSettings();
          referrer.balance += settings.referralBonus;
          referrer.totalEarned += settings.referralBonus;
          await referrer.save();
        }
      }

      await user.save();
      res.json({ message: 'Email verified successfully' });
    } catch (error) {
      res.status(400).json({ error: 'Invalid or expired verification token' });
    }
  }
}

module.exports = new AuthController();
```
