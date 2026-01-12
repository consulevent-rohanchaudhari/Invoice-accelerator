import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Divider,
  Chip,
  AppBar,
  Toolbar,
  CircularProgress,
  TextField,
  Button,
  List,
  ListItem
} from '@mui/material';
import { 
  Close as CloseIcon, 
  Visibility as ViewIcon,
  Receipt as ReceiptIcon,
  Send as SendIcon,
  Delete as DeleteIcon,
  Comment as CommentIcon
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState('');
  const [commentsLoading, setCommentsLoading] = useState(false);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/invoices/all`);
      setInvoices(response.data);
    } catch (err) {
      console.error('Failed to fetch invoices:', err);
      alert('Failed to load invoices. Make sure backend is running!');
    } finally {
      setLoading(false);
    }
  };

  const fetchComments = async (invoiceId) => {
    setCommentsLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/invoices/${invoiceId}/comments`);
      setComments(response.data);
    } catch (err) {
      console.error('Failed to fetch comments:', err);
    } finally {
      setCommentsLoading(false);
    }
  };

  const handleViewInvoice = (invoice) => {
    setSelectedInvoice(invoice);
    setDialogOpen(true);
    fetchComments(invoice.invoice_id);
  };

  const handleAddComment = async () => {
    if (!newComment.trim()) return;
    
    try {
      await axios.post(
        `${API_URL}/api/invoices/${selectedInvoice.invoice_id}/comments`,
        {
          comment_text: newComment,
          created_by: 'QA Engineer'
        }
      );
      
      setNewComment('');
      fetchComments(selectedInvoice.invoice_id);
    } catch (err) {
      console.error('Failed to add comment:', err);
      alert('Failed to add comment');
    }
  };

  const handleDeleteComment = async (commentId) => {
    try {
      await axios.delete(
        `${API_URL}/api/invoices/${selectedInvoice.invoice_id}/comments/${commentId}`
      );
      fetchComments(selectedInvoice.invoice_id);
    } catch (err) {
      console.error('Failed to delete comment:', err);
      alert('Failed to delete comment');
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress size={60} />
      </Box>
    );
  }

  return (
    <Box sx={{ bgcolor: '#f8fafc', minHeight: '100vh' }}>
      <AppBar position="static" sx={{ bgcolor: '#1e293b' }}>
        <Toolbar>
          <ReceiptIcon sx={{ mr: 2, fontSize: 32 }} />
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            Invoice Testing & Validation
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Paper elevation={0} sx={{ p: 3, mb: 3, borderRadius: 3, border: '1px solid #e2e8f0' }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
            All Processed Invoices
          </Typography>
          <Typography variant="body2" color="textSecondary">
            {invoices.length} invoices found
          </Typography>
        </Paper>

        <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: '1px solid #e2e8f0' }}>
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: '#f8fafc' }}>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Invoice ID</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Supplier</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Amount</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Date</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                    <ReceiptIcon sx={{ fontSize: 64, color: '#cbd5e1', mb: 2 }} />
                    <Typography variant="h6" color="textSecondary">
                      No invoices found
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                invoices.map((invoice) => (
                  <TableRow key={invoice.invoice_id} hover>
                    <TableCell sx={{ fontWeight: 600, color: '#1e293b' }}>
                      {invoice.invoice_id}
                    </TableCell>
                    <TableCell>{invoice.supplier_name || 'N/A'}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: '#10b981' }}>
                      ${invoice.total_amount?.toFixed(2) || '0.00'}
                    </TableCell>
                    <TableCell>{invoice.invoice_date || 'N/A'}</TableCell>
                    <TableCell>
                      <Chip 
                        label={invoice.status || 'PROCESSED'} 
                        color="success" 
                        size="small"
                        sx={{ fontWeight: 600 }}
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton 
                        color="primary" 
                        onClick={() => handleViewInvoice(invoice)}
                        size="small"
                      >
                        <ViewIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {selectedInvoice && (
          <Dialog 
            open={dialogOpen} 
            onClose={() => setDialogOpen(false)}
            maxWidth={false}
            fullWidth
            PaperProps={{ 
              sx: { 
                borderRadius: 3, 
                height: '90vh',
                width: '95vw',
                maxWidth: '1800px',
                display: 'flex',
                flexDirection: 'column'
              } 
            }}
          >
            <DialogTitle sx={{ bgcolor: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexShrink: 0 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    Invoice: {selectedInvoice.invoice_id}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Compare PDF with extracted data and add QA notes
                  </Typography>
                </Box>
                <IconButton onClick={() => setDialogOpen(false)}>
                  <CloseIcon />
                </IconButton>
              </Box>
            </DialogTitle>
            <DialogContent sx={{ p: 3, flex: 1, overflow: 'hidden' }}>
              <Box sx={{ display: 'flex', gap: 2, height: '100%' }}>
                {/* PDF Viewer - Left (33.33%) */}
                <Box sx={{ width: '33.33%', height: '100%', minWidth: 0 }}>
                  <Paper sx={{ p: 2, height: '100%', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600, flexShrink: 0 }}>
                      📄 PDF Document
                    </Typography>
                    <Box sx={{ 
                      flexGrow: 1,
                      bgcolor: '#f8fafc', 
                      borderRadius: 2,
                      overflow: 'hidden',
                      minHeight: 0
                    }}>
                      <iframe
                        src={`${API_URL}/api/invoices/${selectedInvoice.invoice_id}/pdf`}
                        width="100%"
                        height="100%"
                        title="Invoice PDF"
                        style={{ border: 'none' }}
                      />
                    </Box>
                  </Paper>
                </Box>

                {/* Extracted Data - Middle (33.33%) */}
                <Box sx={{ width: '33.33%', height: '100%', minWidth: 0 }}>
                  <Paper sx={{ p: 3, height: '100%', overflow: 'auto', border: '1px solid #e2e8f0' }}>
                    <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                      📊 Extracted Data
                    </Typography>
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        INVOICE ID
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        {selectedInvoice.invoice_id || 'N/A'}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        SUPPLIER NAME
                      </Typography>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedInvoice.supplier_name || 'N/A'}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        INVOICE DATE
                      </Typography>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedInvoice.invoice_date || 'N/A'}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        TOTAL AMOUNT
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: '#10b981' }}>
                        ${selectedInvoice.total_amount?.toFixed(2) || '0.00'}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    {selectedInvoice.line_items && (
                      <>
                        <Box sx={{ mb: 3 }}>
                          <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                            LINE ITEMS
                          </Typography>
                          <Paper sx={{ p: 2, bgcolor: '#f8fafc', mt: 1, borderRadius: 2, maxHeight: '200px', overflow: 'auto' }}>
                            <pre style={{ 
                              fontSize: '11px', 
                              margin: 0, 
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace'
                            }}>
                              {JSON.stringify(selectedInvoice.line_items, null, 2)}
                            </pre>
                          </Paper>
                        </Box>
                        <Divider sx={{ my: 2 }} />
                      </>
                    )}
                    
                    <Box>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        RAW EXTRACTED DATA
                      </Typography>
                      <Paper sx={{ 
                        p: 2, 
                        bgcolor: '#f8fafc', 
                        mt: 1, 
                        maxHeight: '300px', 
                        overflow: 'auto',
                        borderRadius: 2
                      }}>
                        {selectedInvoice.raw_extracted_data ? (
                          <pre style={{ 
                            fontSize: '11px', 
                            margin: 0,
                            fontFamily: 'monospace',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word'
                          }}>
                            {typeof selectedInvoice.raw_extracted_data === 'string' 
                              ? JSON.stringify(JSON.parse(selectedInvoice.raw_extracted_data), null, 2)
                              : JSON.stringify(selectedInvoice.raw_extracted_data, null, 2)
                            }
                          </pre>
                        ) : (
                          <Typography variant="body2" color="textSecondary">
                            No raw data available
                          </Typography>
                        )}
                      </Paper>
                    </Box>
                  </Paper>
                </Box>

                {/* Comments - Right (33.33%) */}
                <Box sx={{ width: '33.33%', height: '100%', minWidth: 0 }}>
                  <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', border: '1px solid #e2e8f0' }}>
                    <Box display="flex" alignItems="center" sx={{ mb: 2, flexShrink: 0 }}>
                      <CommentIcon sx={{ mr: 1, color: '#3b82f6' }} />
                      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                        QA Comments
                      </Typography>
                      <Chip 
                        label={comments.length} 
                        size="small" 
                        sx={{ ml: 1 }}
                        color="primary"
                      />
                    </Box>

                    {/* Comments List */}
                    <Box sx={{ flexGrow: 1, overflow: 'auto', mb: 2, minHeight: 0 }}>
                      {commentsLoading ? (
                        <Box display="flex" justifyContent="center" py={4}>
                          <CircularProgress size={30} />
                        </Box>
                      ) : comments.length === 0 ? (
                        <Typography variant="body2" color="textSecondary" align="center" sx={{ py: 4 }}>
                          No comments yet. Add one below.
                        </Typography>
                      ) : (
                        <List sx={{ p: 0 }}>
                          {comments.map((comment) => (
                            <ListItem 
                              key={comment.comment_id}
                              sx={{ 
                                bgcolor: '#f8fafc', 
                                mb: 1, 
                                borderRadius: 2,
                                flexDirection: 'column',
                                alignItems: 'flex-start',
                                p: 1.5,
                                border: '1px solid #e2e8f0'
                              }}
                            >
                              <Box display="flex" justifyContent="space-between" width="100%">
                                <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                                  {comment.created_by} • {new Date(comment.created_at).toLocaleString()}
                                </Typography>
                                <IconButton 
                                  size="small" 
                                  onClick={() => handleDeleteComment(comment.comment_id)}
                                >
                                  <DeleteIcon fontSize="small" />
                                </IconButton>
                              </Box>
                              <Typography variant="body2" sx={{ mt: 0.5 }}>
                                {comment.comment_text}
                              </Typography>
                            </ListItem>
                          ))}
                        </List>
                      )}
                    </Box>

                    {/* Add Comment */}
                    <Box sx={{ flexShrink: 0 }}>
                      <TextField
                        fullWidth
                        multiline
                        rows={3}
                        placeholder="Add a QA comment or note..."
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        variant="outlined"
                        size="small"
                        sx={{ mb: 1 }}
                      />
                      <Button
                        fullWidth
                        variant="contained"
                        startIcon={<SendIcon />}
                        onClick={handleAddComment}
                        disabled={!newComment.trim()}
                      >
                        Add Comment
                      </Button>
                    </Box>
                  </Paper>
                </Box>
              </Box>
            </DialogContent>
          </Dialog>
        )}
      </Container>
    </Box>
  );
}

export default App;