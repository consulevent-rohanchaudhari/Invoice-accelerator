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
  Chip
} from '@mui/material';
import { Close as CloseIcon, Visibility as ViewIcon } from '@mui/icons-material';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function InvoiceTesting() {
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      // Query BigQuery for all processed invoices
      const response = await axios.get(`${API_URL}/api/invoices/all`);
      setInvoices(response.data);
    } catch (err) {
      console.error('Failed to fetch invoices:', err);
    }
  };

  const handleViewInvoice = (invoice) => {
    setSelectedInvoice(invoice);
    setDialogOpen(true);
  };

  return (
    <Box sx={{ bgcolor: '#f8fafc', minHeight: '100vh', py: 4 }}>
      <Container maxWidth="xl">
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>
          Invoice Testing & Validation
        </Typography>
        
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: '#f8fafc' }}>
                <TableCell sx={{ fontWeight: 700 }}>Invoice ID</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Supplier</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Amount</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoices.map((invoice) => (
                <TableRow key={invoice.invoice_id} hover>
                  <TableCell>{invoice.invoice_id}</TableCell>
                  <TableCell>{invoice.supplier_name}</TableCell>
                  <TableCell>${invoice.total_amount?.toFixed(2)}</TableCell>
                  <TableCell>{invoice.invoice_date}</TableCell>
                  <TableCell>
                    <Chip 
                      label={invoice.status || 'PROCESSED'} 
                      color="success" 
                      size="small"
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
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {selectedInvoice && (
          <Dialog 
            open={dialogOpen} 
            onClose={() => setDialogOpen(false)}
            maxWidth="xl"
            fullWidth
          >
            <DialogTitle>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="h6">
                  Invoice: {selectedInvoice.invoice_id}
                </Typography>
                <IconButton onClick={() => setDialogOpen(false)}>
                  <CloseIcon />
                </IconButton>
              </Box>
            </DialogTitle>
            <DialogContent>
              <Grid container spacing={2}>
                {/* PDF Viewer - Left Side */}
                <Grid item xs={6}>
                  <Paper sx={{ p: 2, height: '70vh' }}>
                    <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                      PDF Document
                    </Typography>
                    <iframe
                      src={selectedInvoice.gcs_uri}
                      width="100%"
                      height="90%"
                      title="Invoice PDF"
                      style={{ border: 'none' }}
                    />
                  </Paper>
                </Grid>

                {/* Extracted Data - Right Side */}
                <Grid item xs={6}>
                  <Paper sx={{ p: 3, height: '70vh', overflow: 'auto' }}>
                    <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                      Extracted Data
                    </Typography>
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary">INVOICE ID</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedInvoice.invoice_id}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary">SUPPLIER NAME</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedInvoice.supplier_name}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary">INVOICE DATE</Typography>
                      <Typography variant="body1" sx={{ fontWeight: 600 }}>
                        {selectedInvoice.invoice_date}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary">TOTAL AMOUNT</Typography>
                      <Typography variant="h5" sx={{ fontWeight: 700, color: '#10b981' }}>
                        ${selectedInvoice.total_amount?.toFixed(2)}
                      </Typography>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="textSecondary">LINE ITEMS</Typography>
                      <Paper sx={{ p: 2, bgcolor: '#f8fafc', mt: 1 }}>
                        <pre style={{ fontSize: '12px', margin: 0, whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(selectedInvoice.line_items, null, 2)}
                        </pre>
                      </Paper>
                    </Box>
                    
                    <Divider sx={{ my: 2 }} />
                    
                    <Box>
                      <Typography variant="caption" color="textSecondary">RAW EXTRACTED DATA</Typography>
                      <Paper sx={{ p: 2, bgcolor: '#f8fafc', mt: 1, maxHeight: '200px', overflow: 'auto' }}>
                        <pre style={{ fontSize: '11px', margin: 0 }}>
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

export default InvoiceTesting;
