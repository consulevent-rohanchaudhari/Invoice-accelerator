import React, { useState, useEffect } from 'react';
import './App.css';
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
  Alert
} from '@mui/material';
import {
  CheckCircle as ApprovedIcon,
  Cancel as RejectedIcon,
  Pending as PendingIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import axios from 'axios';
import { format } from 'date-fns';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [exceptions, setExceptions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedEx, setSelectedEx] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reviewStatus, setReviewStatus] = useState('APPROVED');
  const [reviewComments, setReviewComments] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
  }, [filterStatus]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = filterStatus ? { status: filterStatus } : {};
      const [exceptionsRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/exceptions`, { params }),
        axios.get(`${API_URL}/api/stats`)
      ]);
      setExceptions(exceptionsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError('Failed to fetch data. Make sure the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = async (exceptionId) => {
    try {
      const res = await axios.get(`${API_URL}/api/exceptions/${exceptionId}`);
      setSelectedEx(res.data);
      setDialogOpen(true);
    } catch (err) {
      console.error(err);
    }
  };

  const handleReview = async () => {
    try {
      await axios.put(`${API_URL}/api/exceptions/${selectedEx.exception_id}`, {
        status: reviewStatus,
        reviewed_by: 'rohan.chaudhari@consuleventinc.com',
        review_comments: reviewComments
      });
      setDialogOpen(false);
      setReviewComments('');
      fetchData();
    } catch (err) {
      alert('Update failed: ' + err.response?.data?.detail || err.message);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'APPROVED':
        return <ApprovedIcon color="success" />;
      case 'REJECTED':
        return <RejectedIcon color="error" />;
      default:
        return <PendingIcon color="warning" />;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      default:
        return 'info';
    }
  };

  if (loading && !stats) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <div className="App">
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Invoice Exception Management
          </Typography>
          <Button color="inherit" startIcon={<RefreshIcon />} onClick={fetchData}>
            Refresh
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Statistics Cards */}
        {stats && (
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Total Exceptions
                  </Typography>
                  <Typography variant="h3">{stats.total_exceptions}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Pending
                  </Typography>
                  <Typography variant="h3" color="warning.main">
                    {stats.by_status.PENDING}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Approved
                  </Typography>
                  <Typography variant="h3" color="success.main">
                    {stats.by_status.APPROVED}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Rejected
                  </Typography>
                  <Typography variant="h3" color="error.main">
                    {stats.by_status.REJECTED}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        )}

        {/* Filter */}
        <Box sx={{ mb: 2 }}>
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel>Filter by Status</InputLabel>
            <Select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              label="Filter by Status"
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="PENDING">Pending</MenuItem>
              <MenuItem value="APPROVED">Approved</MenuItem>
              <MenuItem value="REJECTED">Rejected</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {/* Exceptions Table */}
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>Invoice ID</TableCell>
                <TableCell>Supplier</TableCell>
                <TableCell>Amount</TableCell>
                <TableCell>Exception Type</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell>Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {exceptions.map((ex) => (
                <TableRow
                  key={ex.exception_id}
                  hover
                  onClick={() => handleRowClick(ex.exception_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <TableCell>{getStatusIcon(ex.status)}</TableCell>
                  <TableCell>{ex.invoice_id}</TableCell>
                  <TableCell>{ex.supplier_name}</TableCell>
                  <TableCell>${ex.total_amount?.toFixed(2)}</TableCell>
                  <TableCell>{ex.exception_type}</TableCell>
                  <TableCell>
                    <Chip
                      label={ex.exception_severity}
                      color={getSeverityColor(ex.exception_severity)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {format(new Date(ex.created_at), 'MMM dd, yyyy HH:mm')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Exception Detail Dialog */}
        {selectedEx && (
          <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
            <DialogTitle>Exception Details</DialogTitle>
            <DialogContent>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={6}>
                  <Typography variant="subtitle2">Invoice ID</Typography>
                  <Typography>{selectedEx.invoice_id}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2">Supplier</Typography>
                  <Typography>{selectedEx.supplier_name}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2">Total Amount</Typography>
                  <Typography>${selectedEx.total_amount?.toFixed(2)}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2">Invoice Date</Typography>
                  <Typography>{selectedEx.invoice_date}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle2">Exception Type</Typography>
                  <Chip
                    label={selectedEx.exception_type}
                    color={getSeverityColor(selectedEx.exception_severity)}
                  />
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle2">File</Typography>
                  <Typography>{selectedEx.filename}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <FormControl fullWidth sx={{ mt: 2 }}>
                    <InputLabel>Review Decision</InputLabel>
                    <Select
                      value={reviewStatus}
                      onChange={(e) => setReviewStatus(e.target.value)}
                      label="Review Decision"
                    >
                      <MenuItem value="APPROVED">Approve</MenuItem>
                      <MenuItem value="REJECTED">Reject</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    multiline
                    rows={3}
                    label="Comments"
                    value={reviewComments}
                    onChange={(e) => setReviewComments(e.target.value)}
                  />
                </Grid>
              </Grid>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleReview} variant="contained" color="primary">
                Submit Review
              </Button>
            </DialogActions>
          </Dialog>
        )}
      </Container>
    </div>
  );
}

export default App;
