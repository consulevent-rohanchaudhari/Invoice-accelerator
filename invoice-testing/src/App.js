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
  Grid,
  Divider,
  Chip,
  AppBar,
  Toolbar,
  CircularProgress
} from '@mui/material';
import { 
  Close as CloseIcon, 
  Visibility as ViewIcon,
  Receipt as ReceiptIcon 
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);

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

  const handleViewInvoice = (invoice) => {
    setSelectedInvoice(invoice);
    setDialogOpen(true);
  };

  // Convert GCS URI to signed URL (for now, we'll use the storage browser link)
  const getPdfUrl = (gcsUri) => {
    if (!gcsUri) return null;
    // For testing, create a link to GCS console
    const path = gcsUri.replace('gs://', '');
    return `https://console.cloud.google.com/storage/browser/_details/${path}`;
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
                    <Typography variant="body2" color="textSecondary">
                      Process some invoices to see them here
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
            maxWidth="xl"
            fullWidth
            PaperProps={{ sx: { borderRadius: 3, height: '90vh' } }}
          >
            <DialogTitle sx={{ bgcolor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    Invoice: {selectedInvoice.invoice_id}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Compare PDF with extracted data
                  </Typography>
                </Box>
                <IconButton onClick={() => setDialogOpen(false)}>
                  <CloseIcon />
                </IconButton>
              </Box>
            </DialogTitle>
            <DialogContent sx={{ p: 3 }}>
              <Grid container spacing={3} sx={{ height: '100%' }}>
                {/* PDF Viewer - Left Side */}
                <Grid item xs={6}>
                  <Paper sx={{ p: 2, height: '100%', border: '1px solid #e2e8f0' }}>
                    <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                      📄 PDF Document
                    </Typography>
                    <Box sx={{ 
                      height: 'calc(100% - 40px)', 
                      bgcolor: '#f8fafc', 
                      borderRadius: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      p: 3
                    }}>
                      <Box textAlign="center">
                        <Typography variant="body1" sx={{ mb: 2 }}>
                          PDF Preview not available in development
                        </Typography>
                      <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                          Open the file in GCS Console to view
                        </Typography>
                        <Chip 
                          label="Open in GCS Console" 
                          component="a"
                          href={getPdfUrl(selectedInvoice.gcs_uri)}
                          target="_blank"
                          clickable
                          color="primary"
                          sx={{ fontWeight: 600 }}
                        />
                        <Typography variant="caption" display="block" sx={{ mt: 2, color: '#64748b' }}>
                          {selectedInvoice.gcs_uri}
                        </Typography>
                      </Box>
                    </Box>
                  </Paper>
                </Grid>

                {/* Extracted Data - Right Side */}
                <Grid item xs={6}>
                  <Paper sx={{ p: 3, height: '100%', overflow: 'auto', border: '1px solid #e2e8f0' }}>
                    <Typography variant="subtitle1" sx={{ mb: 3, fontWeight: 600 }}>
                      📊 Extracted Data
                    </Typography>
                    
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        INVOICE ID
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        {selectedInvoice.invoice_id || 'N/A'}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 600 }}>
                        SUPPLIER NAME
                      </Typography>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedInvoice.supplier_name || 'N/A'}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 3 }}>
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
                          <Paper sx={{ p: 2, bgcolor: '#f8fafc', mt: 1, borderRadius: 2 }}>
                            <pre style={{ 
                              fontSize: '12px', 
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
                        <pre style={{ 
                          fontSize: '11px', 
                          margin: 0,
                          fontFamily: 'monospace'
                        }}>
                          {JSON.stringify(selectedInvoice.raw_extracted_data, null, 2)}
                        </pre>
                      </Paper>
                    </Box>
                  </Paper>
                </Grid>
              </Grid>
            </DialogContent>
          </Dialog>
        )}
      </Container>
    </Box>
  );
}

export default App;
