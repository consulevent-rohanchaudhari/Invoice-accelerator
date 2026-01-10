import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, OAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyBSRruPxiO5-g1ID_JsLyrONEpoRwmrRwA",
  authDomain: "invoice-exception-manage-767ae.firebaseapp.com",
  projectId: "invoice-exception-manage-767ae",
  storageBucket: "invoice-exception-manage-767ae.firebasestorage.app",
  messagingSenderId: "309540932386",
  appId: "1:309540932386:web:228d463dfcf7b1ee74f37b"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
export const microsoftProvider = new OAuthProvider('microsoft.com');

// Configure for your specific Azure AD tenant
microsoftProvider.setCustomParameters({
  tenant: 'c2f5e7bf-4714-4c2a-b179-a3ffd41ed3ea'  // Your Consulevent tenant ID
});