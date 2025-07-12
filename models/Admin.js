const mongoose = require('mongoose');
const bcrypt = require('bcrypt');

// Admin Schema
const adminSchema = new mongoose.Schema({
  username: {
    type: String,
    required: [true, 'Username is required'],
    unique: true,
    trim: true,
    minlength: [3, 'Username must be at least 3 characters long'],
    maxlength: [30, 'Username cannot exceed 30 characters']
  },
  email: {
    type: String,
    required: [true, 'Email is required'],
    unique: true,
    trim: true,
    lowercase: true,
    match: [/^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$/, 'Please enter a valid email']
  },
  password: {
    type: String,
    required: [true, 'Password is required'],
    minlength: [6, 'Password must be at least 6 characters long']
  },
  role: {
    type: String,
    enum: {
      values: ['admin', 'super_admin', 'moderator'],
      message: 'Role must be either admin, super_admin, or moderator'
    },
    default: 'admin'
  },
  firstName: {
    type: String,
    trim: true,
    maxlength: [50, 'First name cannot exceed 50 characters']
  },
  lastName: {
    type: String,
    trim: true,
    maxlength: [50, 'Last name cannot exceed 50 characters']
  },
  phone: {
    type: String,
    trim: true,
    match: [/^[+]?[\d\s-()]{10,}$/, 'Please enter a valid phone number']
  },
  profilePicture: {
    type: String,
    default: null
  },
  isActive: {
    type: Boolean,
    default: true
  },
  permissions: {
    users: {
      view: { type: Boolean, default: true },
      create: { type: Boolean, default: false },
      edit: { type: Boolean, default: false },
      delete: { type: Boolean, default: false }
    },
    videos: {
      view: { type: Boolean, default: true },
      create: { type: Boolean, default: true },
      edit: { type: Boolean, default: true },
      delete: { type: Boolean, default: false }
    },
    payments: {
      view: { type: Boolean, default: true },
      approve: { type: Boolean, default: false },
      reject: { type: Boolean, default: false }
    },
    settings: {
      view: { type: Boolean, default: true },
      edit: { type: Boolean, default: false }
    },
    analytics: {
      view: { type: Boolean, default: true }
    }
  },
  lastLogin: {
    type: Date,
    default: null
  },
  lastLoginIP: {
    type: String,
    default: null
  },
  loginAttempts: {
    type: Number,
    default: 0
  },
  lockUntil: {
    type: Date,
    default: null
  },
  passwordChangedAt: {
    type: Date,
    default: Date.now
  },
  twoFactorEnabled: {
    type: Boolean,
    default: false
  },
  twoFactorSecret: {
    type: String,
    default: null
  },
  resetPasswordToken: {
    type: String,
    default: null
  },
  resetPasswordExpires: {
    type: Date,
    default: null
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  updatedAt: {
    type: Date,
    default: Date.now
  },
  createdBy: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Admin',
    default: null
  }
}, {
  timestamps: true
});

// Indexes for better query performance
adminSchema.index({ username: 1 });
adminSchema.index({ email: 1 });
adminSchema.index({ role: 1 });
adminSchema.index({ isActive: 1 });
adminSchema.index({ createdAt: -1 });

// Virtual for full name
adminSchema.virtual('fullName').get(function() {
  if (this.firstName && this.lastName) {
    return `${this.firstName} ${this.lastName}`;
  }
  return this.username;
});

// Virtual for account lock status
adminSchema.virtual('isLocked').get(function() {
  return !!(this.lockUntil && this.lockUntil > Date.now());
});

// Pre-save middleware to hash password
adminSchema.pre('save', async function(next) {
  // Only hash password if it's new or modified
  if (!this.isModified('password')) return next();
  
  try {
    // Hash password with cost of 12
    const salt = await bcrypt.genSalt(12);
    this.password = await bcrypt.hash(this.password, salt);
    
    // Update password changed timestamp
    this.passwordChangedAt = Date.now();
    
    next();
  } catch (error) {
    next(error);
  }
});

// Pre-save middleware to update timestamps
adminSchema.pre('save', function(next) {
  this.updatedAt = Date.now();
  next();
});

// Instance method to check password
adminSchema.methods.comparePassword = async function(candidatePassword) {
  try {
    return await bcrypt.compare(candidatePassword, this.password);
  } catch (error) {
    throw new Error('Password comparison failed');
  }
};

// Instance method to check if password was changed after JWT was issued
adminSchema.methods.changedPasswordAfter = function(JWTTimestamp) {
  if (this.passwordChangedAt) {
    const changedTimestamp = parseInt(this.passwordChangedAt.getTime() / 1000, 10);
    return JWTTimestamp < changedTimestamp;
  }
  return false;
};

// Instance method to increment login attempts
adminSchema.methods.incLoginAttempts = async function() {
  // If we have a previous lock that has expired, restart at 1
  if (this.lockUntil && this.lockUntil < Date.now()) {
    return this.updateOne({
      $set: { loginAttempts: 1 },
      $unset: { lockUntil: 1 }
    });
  }
  
  const updates = { $inc: { loginAttempts: 1 } };
  
  // If we have max attempts and not locked, lock the account
  if (this.loginAttempts + 1 >= 5 && !this.isLocked) {
    updates.$set = { lockUntil: Date.now() + 2 * 60 * 60 * 1000 }; // 2 hours
  }
  
  return this.updateOne(updates);
};

// Instance method to reset login attempts
adminSchema.methods.resetLoginAttempts = async function() {
  return this.updateOne({
    $unset: { loginAttempts: 1, lockUntil: 1 }
  });
};

// Instance method to check permissions
adminSchema.methods.hasPermission = function(resource, action) {
  // Super admin has all permissions
  if (this.role === 'super_admin') return true;
  
  // Check if admin is active
  if (!this.isActive) return false;
  
  // Check specific permission
  if (this.permissions[resource] && this.permissions[resource][action]) {
    return true;
  }
  
  return false;
};

// Instance method to get safe admin data (without sensitive info)
adminSchema.methods.toSafeObject = function() {
  const adminObject = this.toObject();
  
  // Remove sensitive fields
  delete adminObject.password;
  delete adminObject.twoFactorSecret;
  delete adminObject.resetPasswordToken;
  delete adminObject.resetPasswordExpires;
  delete adminObject.loginAttempts;
  delete adminObject.lockUntil;
  
  return adminObject;
};

// Static method to find admin by credentials
adminSchema.statics.findByCredentials = async function(username, password) {
  const admin = await this.findOne({
    $or: [
      { username: username },
      { email: username }
    ],
    isActive: true
  });
  
  if (!admin) {
    throw new Error('Invalid credentials');
  }
  
  // Check if account is locked
  if (admin.isLocked) {
    throw new Error('Account is temporarily locked due to too many failed login attempts');
  }
  
  const isMatch = await admin.comparePassword(password);
  
  if (!isMatch) {
    // Increment login attempts
    await admin.incLoginAttempts();
    throw new Error('Invalid credentials');
  }
  
  // Reset login attempts on successful login
  if (admin.loginAttempts && admin.loginAttempts > 0) {
    await admin.resetLoginAttempts();
  }
  
  return admin;
};

// Static method to create default super admin
adminSchema.statics.createDefaultAdmin = async function() {
  try {
    const existingAdmin = await this.findOne({ role: 'super_admin' });
    
    if (existingAdmin) {
      console.log('Default super admin already exists');
      return existingAdmin;
    }
    
    const defaultAdmin = new this({
      username: 'admin',
      email: 'admin@watchearn.com',
      password: 'admin123456', // Will be hashed by pre-save middleware
      role: 'super_admin',
      firstName: 'Super',
      lastName: 'Admin',
      permissions: {
        users: { view: true, create: true, edit: true, delete: true },
        videos: { view: true, create: true, edit: true, delete: true },
        payments: { view: true, approve: true, reject: true },
        settings: { view: true, edit: true },
        analytics: { view: true }
      }
    });
    
    await defaultAdmin.save();
    console.log('Default super admin created successfully');
    console.log('Username: admin');
    console.log('Password: admin123456');
    console.log('Please change the password after first login!');
    
    return defaultAdmin;
  } catch (error) {
    console.error('Error creating default admin:', error);
    throw error;
  }
};

// Static method to get admin statistics
adminSchema.statics.getStats = async function() {
  const stats = await this.aggregate([
    {
      $group: {
        _id: null,
        totalAdmins: { $sum: 1 },
        activeAdmins: {
          $sum: { $cond: [{ $eq: ['$isActive', true] }, 1, 0] }
        },
        superAdmins: {
          $sum: { $cond: [{ $eq: ['$role', 'super_admin'] }, 1, 0] }
        },
        regularAdmins: {
          $sum: { $cond: [{ $eq: ['$role', 'admin'] }, 1, 0] }
        },
        moderators: {
          $sum: { $cond: [{ $eq: ['$role', 'moderator'] }, 1, 0] }
        }
      }
    }
  ]);
  
  return stats[0] || {
    totalAdmins: 0,
    activeAdmins: 0,
    superAdmins: 0,
    regularAdmins: 0,
    moderators: 0
  };
};

// Export the model
module.exports = mongoose.model('Admin', adminSchema);
