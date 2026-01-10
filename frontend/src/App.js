import React, { useState, useEffect, useMemo, useCallback } from 'react';
import './App.css';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import InvoiceTesting from './InvoiceTesting';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Grid,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Box,
  Alert,
  Avatar,
  Divider,
  Stack,
  Snackbar
} from '@mui/material';
import {
  CheckCircle as ApprovedIcon,
  Cancel as RejectedIcon,
  Pending as PendingIcon,
  Refresh as RefreshIcon,
  Receipt as ReceiptIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  AttachMoney as MoneyIcon,
  Business as BusinessIcon,
  CalendarToday as CalendarIcon,
  Error as ErrorIcon,
  Logout as LogoutIcon,
  PictureAsPdf as PdfIcon,
  Visibility as ViewIcon,
  Download as DownloadIcon
} from '@mui/icons-material';
import axios from 'axios';
import { format } from 'date-fns';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [allExceptions, setAllExceptions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedEx, setSelectedEx] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reviewStatus, setReviewStatus] = useState('APPROVED');
  const [reviewComments, setReviewComments] = useState('');
  const [filterStatus, setFilterStatus] = useState('PENDING');
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);

  const filteredExceptions = useMemo(() => {
    if (!filterStatus) return allExceptions;
    return allExceptions.filter(ex => ex.status === filterStatus);
  }, [allExceptions, filterStatus]);

  const fetchData = useCallback(async () => {
    if (!user) return;
    
    setLoading(true);
    setError(null);
    try {
      const [exceptionsRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/exceptions`, { params: { limit: 1000 } }),
        axios.get(`${API_URL}/api/stats`)
      ]);
      setAllExceptions(exceptionsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError('Failed to fetch data. ' + (err.response?.data?.detail || err.message));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user, fetchData]);

  const handleLogin = (e) => {
    e.preventDefault();
    // Simple password check - in production, use real auth
    if (password === 'admin123' && email.includes('@')) {
      setUser({ email });
      showSnackbar('Logged in successfully!', 'success');
    } else {
      showSnackbar('Invalid credentials. Use password: admin123', 'error');
    }
  };

  const handleLogout = () => {
    setUser(null);
    setAllExceptions([]);
    setStats(null);
    setEmail('');
    setPassword('');
  };

  const handleRowClick = async (exceptionId) => {
    try {
      const res = await axios.get(`${API_URL}/api/exceptions/${exceptionId}`);
      setSelectedEx(res.data);
      setReviewStatus('APPROVED');
      setReviewComments('');
      setDialogOpen(true);
    } catch (err) {
      console.error(err);
      showSnackbar('Failed to load exception details', 'error');
    }
  };

  const handleViewPdf = async (exceptionId) => {
    try {
      const pdfUrlEndpoint = `${API_URL}/api/exceptions/${exceptionId}/pdf`;
      setPdfUrl(pdfUrlEndpoint);
      setPdfViewerOpen(true);
    } catch (err) {
      console.error(err);
      showSnackbar('Failed to load PDF', 'error');
    }
  };

  const handleDownloadPdf = async (exceptionId, filename) => {
    try {
      const response = await axios.get(`${API_URL}/api/exceptions/${exceptionId}/pdf`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename || 'invoice.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showSnackbar('PDF downloaded successfully', 'success');
    } catch (err) {
      console.error(err);
      showSnackbar('Failed to download PDF', 'error');
    }
  };

  const handleReview = async () => {
    try {
      await axios.put(
        `${API_URL}/api/exceptions/${selectedEx.exception_id}`,
        {
          status: reviewStatus,
          reviewed_by: user.email,
          review_comments: reviewComments
        }
      );
      
      setDialogOpen(false);
      setReviewComments('');
      
      const message = reviewStatus === 'APPROVED' 
        ? `✓ Exception ${selectedEx.invoice_id} approved successfully`
        : `✗ Exception ${selectedEx.invoice_id} rejected successfully`;
      showSnackbar(message, 'success');
      
      await fetchData();
      
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message;
      showSnackbar(`Update failed: ${errorMsg}`, 'error');
    }
  };

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'APPROVED':
        return <ApprovedIcon sx={{ color: '#10b981' }} />;
      case 'REJECTED':
        return <RejectedIcon sx={{ color: '#ef4444' }} />;
      default:
        return <PendingIcon sx={{ color: '#f59e0b' }} />;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high':
        return { bg: '#fee2e2', color: '#dc2626', label: 'High Priority' };
      case 'medium':
        return { bg: '#fef3c7', color: '#d97706', label: 'Medium' };
      default:
        return { bg: '#dbeafe', color: '#2563eb', label: 'Low' };
    }
  };

  const StatCard = ({ title, value, icon, color, subtitle }) => (
    <Card 
      elevation={0} 
      sx={{ 
        background: `linear-gradient(135deg, ${color}15 0%, ${color}25 100%)`,
        border: `1px solid ${color}30`,
        height: '100%'
      }}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
          <Box>
            <Typography color="textSecondary" variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
              {title}
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: color, mb: 0.5 }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="textSecondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Avatar sx={{ bgcolor: color, width: 30, height: 30, ml: 2}}>
            {icon}
          </Avatar>
        </Box>
      </CardContent>
    </Card>
  );

  if (!user) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="100vh" sx={{ bgcolor: '#f8fafc' }}>
        <Paper elevation={3} sx={{ p: 6, borderRadius: 3, textAlign: 'center', maxWidth: 400 }}>
          <ReceiptIcon sx={{ fontSize: 80, color: '#3b82f6', mb: 2 }} />
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
            Invoice Exception Management
          </Typography>
          <Typography variant="body1" color="textSecondary" sx={{ mb: 4 }}>
            Sign in to continue
          </Typography>
          <form onSubmit={handleLogin}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              sx={{ mb: 2 }}
              required
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              sx={{ mb: 3 }}
              required
              helperText="Use: admin123"
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              fullWidth
              sx={{
                bgcolor: '#3b82f6',
                '&:hover': { bgcolor: '#2563eb' },
                py: 1.5,
                borderRadius: 2,
                fontSize: '1rem'
              }}
            >
              Sign In
            </Button>
          </form>
        </Paper>
      </Box>
    );
  }

  if (loading && !stats) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="100vh" sx={{ bgcolor: '#f8fafc' }}>
        <CircularProgress size={60} thickness={4} />
        <Typography variant="h6" sx={{ mt: 2, color: '#64748b' }}>Loading Dashboard...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ bgcolor: '#f8fafc', minHeight: '100vh', width: '100%' }}>
      <AppBar position="static" elevation={0} sx={{ bgcolor: '#1e293b', borderBottom: '3px solid #3b82f6' }}>
        <Toolbar sx={{ py: 1 }}>
          <ReceiptIcon sx={{ mr: 2, fontSize: 32 }} />
          <Typography variant="h5" component="div" sx={{ flexGrow: 1, fontWeight: 700 }}>
            Invoice Exception Management
          </Typography>
          <Box display="flex" alignItems="center" gap={2}>
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.8)' }}>
              {user.email}
            </Typography>
            <Button 
              color="inherit" 
              startIcon={<RefreshIcon />} 
              onClick={fetchData}
              sx={{ 
                bgcolor: 'rgba(255,255,255,0.1)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                px: 2,
                borderRadius: 2
              }}
            >
              Refresh
            </Button>
            <Button
              color="inherit"
              startIcon={<LogoutIcon />}
              onClick={handleLogout}
              sx={{
                bgcolor: 'rgba(255,255,255,0.1)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                px: 2,
                borderRadius: 2
              }}
            >
              Logout
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%', borderRadius: 2 }}>
          {snackbar.message}
        </Alert>
      </Snackbar>

      {stats && (
        <Box sx={{ mt: 4, mb: 4, width: '100%', overflow: 'hidden' }}>
          <Box sx={{ 
            display: 'grid', 
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
            gap: 2,
            px: 3,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <StatCard
              title="Total Exceptions"
              value={stats.total_exceptions}
              icon={<TrendingUpIcon />}
              color="#6366f1"
              subtitle="Last 30 days"
            />
            <StatCard
              title="Pending Review"
              value={stats.by_status.PENDING}
              icon={<PendingIcon />}
              color="#f59e0b"
              subtitle="Requires action"
            />
            <StatCard
              title="Approved"
              value={stats.by_status.APPROVED}
              icon={<ApprovedIcon />}
              color="#10b981"
              subtitle="Completed"
            />
            <StatCard
              title="Rejected"
              value={stats.by_status.REJECTED}
              icon={<RejectedIcon />}
              color="#ef4444"
              subtitle="Declined"
            />
          </Box>
        </Box>
      )}

      <Box sx={{ mb: 4, px: 3 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }} icon={<ErrorIcon />}>
            {error}
          </Alert>
        )}

        <Paper elevation={0} sx={{ p: 3, mb: 3, borderRadius: 3, border: '1px solid #e2e8f0' }}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
                Exception Queue
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Showing {filteredExceptions.length} of {allExceptions.length} exceptions
              </Typography>
            </Box>
            <FormControl sx={{ minWidth: 200 }}>
              <InputLabel>Filter by Status</InputLabel>
              <Select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                label="Filter by Status"
                sx={{ borderRadius: 2 }}
              >
                <MenuItem value="">All Exceptions</MenuItem>
                <MenuItem value="PENDING">Pending Only</MenuItem>
                <MenuItem value="APPROVED">Approved</MenuItem>
                <MenuItem value="REJECTED">Rejected</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Paper>

        <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: '1px solid #e2e8f0' }}>
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: '#f8fafc' }}>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Invoice ID</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Supplier</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Amount</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Exception</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Severity</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredExceptions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                    <ReceiptIcon sx={{ fontSize: 64, color: '#cbd5e1', mb: 2 }} />
                    <Typography variant="h6" color="textSecondary">
                      {filterStatus === 'PENDING' ? 'No pending exceptions' : 'No exceptions found'}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      {filterStatus === 'PENDING' ? 'All exceptions have been reviewed!' : 'Try changing the filter'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredExceptions.map((ex) => {
                  const severityStyle = getSeverityColor(ex.exception_severity);
                  return (
                    <TableRow
                      key={ex.exception_id}
                      hover
                      onClick={() => handleRowClick(ex.exception_id)}
                      sx={{ 
                        cursor: 'pointer',
                        '&:hover': { bgcolor: '#f8fafc' },
                        transition: 'background-color 0.2s',
                        opacity: ex.status !== 'PENDING' ? 0.7 : 1
                      }}
                    >
                      <TableCell>{getStatusIcon(ex.status)}</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#1e293b' }}>{ex.invoice_id}</TableCell>
                      <TableCell>{ex.supplier_name}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>
                        <Box display="flex" alignItems="center">
                          <MoneyIcon sx={{ fontSize: 16, mr: 0.5, color: '#10b981' }} />
                          ${ex.total_amount?.toFixed(2)}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={ex.exception_type.replace(/_/g, ' ')} 
                          size="small"
                          sx={{ 
                            bgcolor: '#f1f5f9',
                            color: '#475569',
                            fontWeight: 500,
                            fontSize: '0.75rem'
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={severityStyle.label}
                          size="small"
                          sx={{ 
                            bgcolor: severityStyle.bg,
                            color: severityStyle.color,
                            fontWeight: 600,
                            fontSize: '0.75rem',
                            border: `1px solid ${severityStyle.color}30`
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" sx={{ color: '#64748b' }}>
                          <CalendarIcon sx={{ fontSize: 16, mr: 0.5 }} />
                          {format(new Date(ex.created_at), 'MMM dd, yyyy HH:mm')}
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {selectedEx && (
          <Dialog 
            open={dialogOpen} 
            onClose={() => setDialogOpen(false)} 
            maxWidth="md" 
            fullWidth
            PaperProps={{ sx: { borderRadius: 3 } }}
          >
            <DialogTitle sx={{ bgcolor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box display="flex" alignItems="center">
                  <ReceiptIcon sx={{ mr: 2, color: '#3b82f6' }} />
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>
                      Exception Details
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Review and take action on this exception
                    </Typography>
                  </Box>
                </Box>
                {selectedEx.status !== 'PENDING' && (
                  <Chip 
                    icon={getStatusIcon(selectedEx.status)}
                    label={selectedEx.status}
                    color={selectedEx.status === 'APPROVED' ? 'success' : 'error'}
                    sx={{ fontWeight: 600 }}
                  />
                )}
              </Box>
            </DialogTitle>
            <DialogContent sx={{ mt: 3 }}>
              <Grid container spacing={3}>
                <Grid item xs={6}>
                  <Stack spacing={1}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                      INVOICE ID
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>
                      {selectedEx.invoice_id}
                    </Typography>
                  </Stack>
                </Grid>
                <Grid item xs={6}>
                  <Stack spacing={1}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                      SUPPLIER
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <BusinessIcon sx={{ mr: 1, color: '#64748b', fontSize: 20 }} />
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        {selectedEx.supplier_name}
                      </Typography>
                    </Box>
                  </Stack>
                </Grid>
                <Grid item xs={6}>
                  <Stack spacing={1}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                      TOTAL AMOUNT
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <MoneyIcon sx={{ mr: 1, color: '#10b981', fontSize: 24 }} />
                      <Typography variant="h5" sx={{ fontWeight: 700, color: '#10b981' }}>
                        ${selectedEx.total_amount?.toFixed(2)}
                      </Typography>
                    </Box>
                  </Stack>
                </Grid>
                <Grid item xs={6}>
                  <Stack spacing={1}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                      INVOICE DATE
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <CalendarIcon sx={{ mr: 1, color: '#64748b', fontSize: 20 }} />
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedEx.invoice_date}
                      </Typography>
                    </Box>
                  </Stack>
                </Grid>
                <Grid item xs={12}>
                  <Divider />
                </Grid>
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                      EXCEPTION TYPE
                    </Typography>
                    <Chip
                      icon={<WarningIcon />}
                      label={selectedEx.exception_type.replace(/_/g, ' ')}
                      color={getSeverityColor(selectedEx.exception_severity).color === '#dc2626' ? 'error' : 'warning'}
                      sx={{ width: 'fit-content', fontWeight: 600 }}
                    />
                  </Stack>
                </Grid>
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                      FILE
                    </Typography>
                    <Box display="flex" alignItems="center" gap={2}>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', bgcolor: '#f8fafc', p: 1, borderRadius: 1, flex: 1 }}>
                        {selectedEx.filename}
                      </Typography>
                      <Button
                        variant="outlined"
                        startIcon={<ViewIcon />}
                        onClick={() => handleViewPdf(selectedEx.exception_id)}
                        sx={{ borderRadius: 2 }}
                      >
                        View PDF
                      </Button>
                      <Button
                        variant="outlined"
                        startIcon={<DownloadIcon />}
                        onClick={() => handleDownloadPdf(selectedEx.exception_id, selectedEx.filename)}
                        sx={{ borderRadius: 2 }}
                      >
                        Download
                      </Button>
                    </Box>
                  </Stack>
                </Grid>
                
                {selectedEx.status === 'PENDING' && (
                  <>
                    <Grid item xs={12}>
                      <Divider />
                    </Grid>
                    <Grid item xs={12}>
                      <FormControl fullWidth>
                        <InputLabel>Review Decision</InputLabel>
                        <Select
                          value={reviewStatus}
                          onChange={(e) => setReviewStatus(e.target.value)}
                          label="Review Decision"
                          sx={{ borderRadius: 2 }}
                        >
                          <MenuItem value="APPROVED">✓ Approve</MenuItem>
                          <MenuItem value="REJECTED">✗ Reject</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        multiline
                        rows={3}
                        label="Comments"
                        placeholder="Add review comments..."
                        value={reviewComments}
                        onChange={(e) => setReviewComments(e.target.value)}
                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
                      />
                    </Grid>
                  </>
                )}
                
                {selectedEx.status !== 'PENDING' && selectedEx.review_comments && (
                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        REVIEW COMMENTS
                      </Typography>
                      <Paper sx={{ p: 2, bgcolor: '#f8fafc', borderRadius: 2 }}>
                        <Typography variant="body2">{selectedEx.review_comments}</Typography>
                        <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
                          Reviewed by {selectedEx.reviewed_by} on {selectedEx.reviewed_at && format(new Date(selectedEx.reviewed_at), 'MMM dd, yyyy HH:mm')}
                        </Typography>
                      </Paper>
                    </Stack>
                  </Grid>
                )}
              </Grid>
            </DialogContent>
            <DialogActions sx={{ p: 3, bgcolor: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
              <Button onClick={() => setDialogOpen(false)} sx={{ borderRadius: 2 }}>
                {selectedEx.status === 'PENDING' ? 'Cancel' : 'Close'}
              </Button>
              {selectedEx.status === 'PENDING' && (
                <Button 
                  onClick={handleReview} 
                  variant="contained" 
                  sx={{ 
                    borderRadius: 2,
                    px: 4,
                    bgcolor: '#3b82f6',
                    '&:hover': { bgcolor: '#2563eb' }
                  }}
                >
                  Submit Review
                </Button>
              )}
            </DialogActions>
          </Dialog>
        )}

        {/* PDF Viewer Dialog */}
        <Dialog
          open={pdfViewerOpen}
          onClose={() => setPdfViewerOpen(false)}
          maxWidth="lg"
          fullWidth
          PaperProps={{ 
            sx: { 
              borderRadius: 3, 
              height: '90vh',
              display: 'flex',
              flexDirection: 'column'
            } 
          }}
        >
          <DialogTitle sx={{ bgcolor: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexShrink: 0 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Box display="flex" alignItems="center">
                <PdfIcon sx={{ mr: 2, color: '#ef4444' }} />
                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                  Invoice PDF Viewer
                </Typography>
              </Box>
              <Button
                onClick={() => setPdfViewerOpen(false)}
                sx={{ borderRadius: 2 }}
              >
                Close
              </Button>
            </Box>
          </DialogTitle>
          <DialogContent sx={{ p: 0, flex: 1, overflow: 'hidden', position: 'relative' }}>
            {pdfUrl ? (
              <Box sx={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
                <iframe
                  src={pdfUrl}
                  style={{
                    width: '100%',
                    height: '100%',
                    border: 'none'
                  }}
                  title="PDF Viewer"
                />
              </Box>
            ) : (
              <Box display="flex" justifyContent="center" alignItems="center" sx={{ height: '100%' }}>
                <CircularProgress />
              </Box>
            )}
          </DialogContent>
        </Dialog>
      </Box>
    </Box>
  );
}

export default App;