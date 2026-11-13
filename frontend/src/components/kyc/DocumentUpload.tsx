import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, CheckCircle, X, CreditCard, AlertCircle, Briefcase, Loader, ShieldCheck, ShieldX } from 'lucide-react';
import { api } from '../../lib/api';

interface DocumentUploadProps {
  onComplete: (front: File, back: File | null, secondaryId: File, data: {
    panNumber: string;
    secondaryIdType: string;
    secondaryIdNumber: string;
    occupation: string;
  }) => void;
}

type SecondaryIdType = 'aadhaar' | 'passport' | 'driving-license' | '';
type VerifyStatus = 'idle' | 'loading' | 'success' | 'error';

// Verhoeff Algorithm for Aadhaar validation
const verhoeffMultiplicationTable = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
  [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
  [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
  [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
  [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
  [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
  [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
  [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
  [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
];

const verhoeffPermutationTable = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
  [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
  [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
  [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
  [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
  [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
  [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
];

const verhoeffInverseTable = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9];

function validateVerhoeffChecksum(num: string): boolean {
  if (!num || num.length !== 12) return false;

  let checksum = 0;
  const digits = num.split('').map(d => parseInt(d, 10)).reverse();

  for (let i = 0; i < digits.length; i++) {
    const digit = digits[i];
    const permutedDigit = verhoeffPermutationTable[(i + 1) % 8][digit];
    checksum = verhoeffMultiplicationTable[checksum][permutedDigit];
  }

  return checksum === 0;
}

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

// Verification badge component
function VerifyBadge({ status, result }: { status: VerifyStatus; result: any }) {
  if (status === 'idle') return null;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={status}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.2 }}
        className="mt-2"
      >
        {status === 'loading' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded bg-[#111111] border border-[#222222]">
            <Loader className="w-3.5 h-3.5 text-[#888888] animate-spin" />
            <span className="text-xs text-[#888888]">Verifying with government database...</span>
          </div>
        )}
        {status === 'success' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded bg-emerald-950/30 border border-emerald-900/50">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-xs text-emerald-400">
              Verified
              {result?.verification?.source && (
                <span className="text-emerald-600 ml-1">
                  — {result.verification.source.includes('SETU') ? 'Setu API' : 'Smart Validation'}
                </span>
              )}
            </span>
            {result?.verification?.response_time_ms && (
              <span className="text-[10px] text-emerald-700 ml-auto">
                {result.verification.response_time_ms}ms
              </span>
            )}
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded bg-red-950/30 border border-red-900/50">
            <ShieldX className="w-3.5 h-3.5 text-red-400" />
            <span className="text-xs text-red-400">
              {result?.verification?.status === 'INVALID_FORMAT'
                ? 'Invalid format — check the number'
                : result?.verification?.error || 'Verification failed'}
            </span>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}

export function DocumentUpload({ onComplete }: DocumentUploadProps) {
  // PAN Card State
  const [panNumber, setPanNumber] = useState('');
  const [panFront, setPanFront] = useState<File | null>(null);
  const [panError, setPanError] = useState('');
  const [occupation, setOccupation] = useState('');
  const [otherOccupation, setOtherOccupation] = useState('');

  // Secondary ID State
  const [secondaryIdType, setSecondaryIdType] = useState<SecondaryIdType>('');
  const [secondaryIdNumber, setSecondaryIdNumber] = useState('');
  const [secondaryIdDoc, setSecondaryIdDoc] = useState<File | null>(null);
  const [secondaryIdError, setSecondaryIdError] = useState('');

  // Verification State
  const [panVerifyStatus, setPanVerifyStatus] = useState<VerifyStatus>('idle');
  const [panVerifyResult, setPanVerifyResult] = useState<any>(null);
  const [secondaryVerifyStatus, setSecondaryVerifyStatus] = useState<VerifyStatus>('idle');
  const [secondaryVerifyResult, setSecondaryVerifyResult] = useState<any>(null);

  // Refs
  const panFrontRef = useRef<HTMLInputElement>(null);
  const secondaryIdRef = useRef<HTMLInputElement>(null);

  // Debounced values for triggering verification
  const debouncedPan = useDebounce(panNumber, 500);
  const debouncedSecondaryId = useDebounce(secondaryIdNumber, 500);

  // PAN validation
  const validatePAN = (pan: string): boolean => {
    if (pan.toUpperCase() === 'SENTINELAI') return true;
    const panRegex = /^[A-Z]{3}[PCFHTABLJG]{1}[A-Z]{1}[0-9]{4}[A-Z]{1}$/;
    return panRegex.test(pan.toUpperCase());
  };

  // Secondary ID validation
  const validateSecondaryId = (type: SecondaryIdType, id: string): boolean => {
    switch (type) {
      case 'aadhaar':
        return /^\d{12}$/.test(id);
      case 'driving-license':
        return /^[A-Z]{2}[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{7}$/.test(id.toUpperCase());
      case 'passport':
        return /^[A-Z]{1}\d{7}$/.test(id.toUpperCase());
      default:
        return false;
    }
  };

  // ── PAN Verify Effect ──────────────────────────────────────────────
  useEffect(() => {
    if (!debouncedPan || !validatePAN(debouncedPan)) {
      setPanVerifyStatus('idle');
      setPanVerifyResult(null);
      return;
    }

    // Skip demo value
    if (debouncedPan.toUpperCase() === 'SENTINELAI') {
      setPanVerifyStatus('success');
      setPanVerifyResult({ verification: { source: 'DEMO_MODE', verified: true } });
      return;
    }

    let cancelled = false;
    (async () => {
      setPanVerifyStatus('loading');
      try {
        const res = await api.verifyId('PAN', debouncedPan);
        if (cancelled) return;
        if (res?.verification?.verified) {
          setPanVerifyStatus('success');
        } else {
          setPanVerifyStatus('error');
        }
        setPanVerifyResult(res);
      } catch (err: any) {
        if (cancelled) return;
        setPanVerifyStatus('error');
        setPanVerifyResult(err);
      }
    })();

    return () => { cancelled = true; };
  }, [debouncedPan]);

  // ── Secondary ID Verify Effect ─────────────────────────────────────
  useEffect(() => {
    if (!debouncedSecondaryId || !secondaryIdType || !validateSecondaryId(secondaryIdType, debouncedSecondaryId)) {
      setSecondaryVerifyStatus('idle');
      setSecondaryVerifyResult(null);
      return;
    }

    // Map frontend type to backend type
    const backendType = secondaryIdType === 'driving-license' ? 'DL' : secondaryIdType.toUpperCase();

    let cancelled = false;
    (async () => {
      setSecondaryVerifyStatus('loading');
      try {
        const res = await api.verifyId(backendType, debouncedSecondaryId);
        if (cancelled) return;
        if (res?.verification?.verified) {
          setSecondaryVerifyStatus('success');
        } else {
          setSecondaryVerifyStatus('error');
        }
        setSecondaryVerifyResult(res);
      } catch (err: any) {
        if (cancelled) return;
        setSecondaryVerifyStatus('error');
        setSecondaryVerifyResult(err);
      }
    })();

    return () => { cancelled = true; };
  }, [debouncedSecondaryId, secondaryIdType]);

  const handlePanNumberChange = (value: string) => {
    const upperValue = value.toUpperCase();
    setPanNumber(upperValue);
    if (value && !validatePAN(upperValue)) {
      setPanError('Invalid PAN format. Example: ABCPE1234F');
    } else {
      setPanError('');
    }
  };

  const getSecondaryIdPlaceholder = (type: SecondaryIdType): string => {
    switch (type) {
      case 'aadhaar': return '234123412346';
      case 'driving-license': return 'MH-01-2020-1234567';
      case 'passport': return 'J1234567';
      default: return 'Select ID type first';
    }
  };

  const getSecondaryIdErrorMessage = (type: SecondaryIdType): string => {
    switch (type) {
      case 'aadhaar': return 'Invalid Aadhaar format (must be 12 digits)';
      case 'driving-license': return 'Invalid DL format (e.g., MH-01-2020-1234567)';
      case 'passport': return 'Invalid Passport format (e.g., J1234567)';
      default: return 'Invalid ID format';
    }
  };

  const getSecondaryIdHelpText = (type: SecondaryIdType): string => {
    switch (type) {
      case 'aadhaar': return 'Any 12-digit number is accepted for testing';
      case 'driving-license': return 'Format: State-RTO-Year-Number';
      case 'passport': return 'Valid test: J1234567 or K9876543';
      default: return '';
    }
  };

  const handleSecondaryIdNumberChange = (value: string) => {
    const upperValue = value.toUpperCase().replace(/\s+/g, '');
    setSecondaryIdNumber(upperValue);
    if (value && secondaryIdType && !validateSecondaryId(secondaryIdType, upperValue)) {
      setSecondaryIdError(getSecondaryIdErrorMessage(secondaryIdType));
    } else {
      setSecondaryIdError('');
    }
  };

  const handleFileChange = (
    e: React.ChangeEvent<HTMLInputElement>,
    setter: React.Dispatch<React.SetStateAction<File | null>>
  ) => {
    const file = e.target.files?.[0];
    if (file) {
      setter(file);
    }
  };

  const handleSubmit = () => {
    let hasError = false;

    if (!panNumber || !validatePAN(panNumber)) {
      setPanError('Valid PAN Card number is required');
      hasError = true;
    }
    if (!panFront) {
      setPanError('PAN Card front side is required');
      hasError = true;
    }

    if (!secondaryIdType) {
      setSecondaryIdError('Please select a secondary ID type');
      hasError = true;
    }
    if (!secondaryIdNumber || !validateSecondaryId(secondaryIdType, secondaryIdNumber)) {
      setSecondaryIdError('Valid secondary ID number is required');
      hasError = true;
    }
    if (!secondaryIdDoc) {
      setSecondaryIdError('Secondary ID document is required');
      hasError = true;
    }

    if (!hasError && panFront && secondaryIdDoc) {
      onComplete(panFront, null, secondaryIdDoc, {
        panNumber,
        secondaryIdType,
        secondaryIdNumber,
        occupation: occupation === 'other' ? otherOccupation : occupation,
      });
    }
  };

  const isFormValid =
    panNumber &&
    validatePAN(panNumber) &&
    panFront &&
    secondaryIdType &&
    secondaryIdNumber &&
    validateSecondaryId(secondaryIdType, secondaryIdNumber) &&
    secondaryIdDoc &&
    (occupation === 'other' ? otherOccupation.trim().length > 0 : occupation !== '');

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-8"
      >
        <h2 className="text-2xl font-bold tracking-tight mb-2 text-[#EDEDED]">
          Upload Identity Documents
        </h2>
        <p className="text-sm text-[#888888]">
          Please provide your PAN Card and one additional government-issued ID
        </p>
      </motion.div>

      {/* Demo Button */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex justify-center mb-6"
      >
        <button
          onClick={() => {
            const dummyFile = new File(["dummy"], "demo-document.jpg", { type: "image/jpeg" });
            setPanNumber('SENTINELAI');
            setPanFront(dummyFile);
            setSecondaryIdType('aadhaar');
            setSecondaryIdNumber('123456789012');
            setSecondaryIdDoc(dummyFile);
            setOccupation('software-engineer');
            setPanError('');
            setSecondaryIdError('');
          }}
          className="px-4 py-2 bg-[#222222] border border-[#333333] rounded text-xs text-[#EDEDED] hover:bg-[#333333] transition-colors flex items-center gap-2"
        >
          <FileText className="w-3 h-3" />
          Fill Demo Data
        </button>
      </motion.div>

      {/* PAN Card Section */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="border border-[#222222] rounded p-6 mb-6 bg-[#050505]"
      >
        <div className="flex items-center gap-2 mb-4">
          <CreditCard className="w-5 h-5 text-white" strokeWidth={1.5} />
          <h3 className="text-sm font-medium text-[#EDEDED]">
            PAN Card (Primary ID) <span className="text-red-500">*</span>
          </h3>
        </div>

        {/* PAN Number Input */}
        <div className="mb-4">
          <label className="block text-xs mb-2 text-[#888888]">PAN Card Number</label>
          <input
            type="text"
            value={panNumber}
            onChange={(e) => handlePanNumberChange(e.target.value)}
            placeholder="ABCPE1234F"
            maxLength={10}
            className={`w-full bg-black border ${panError ? 'border-red-500' : panVerifyStatus === 'success' ? 'border-emerald-700' : 'border-[#222222]'} rounded px-4 py-3 text-sm focus:outline-none focus:border-white transition-colors text-[#EDEDED] uppercase`}
          />
          {panError && (
            <div className="flex items-center gap-1 mt-1">
              <AlertCircle className="w-3 h-3 text-red-500" />
              <p className="text-xs text-red-500">{panError}</p>
            </div>
          )}
          <p className="text-xs text-[#888888] mt-1">
            Format: 3 letters + status (P/C/F/H/T/A/B/L/J/G) + letter + 4 digits + letter
          </p>
          <p className="text-xs text-[#666666] mt-1">
            Valid test example: ABCPE1234F
          </p>

          {/* PAN Verification Badge */}
          <VerifyBadge status={panVerifyStatus} result={panVerifyResult} />
        </div>

        {/* PAN Card Upload */}
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-xs mb-2 text-[#888888]">Front Side</label>
            <div
              onClick={() => panFrontRef.current?.click()}
              className="border-2 border-dashed border-[#222222] rounded p-6 text-center cursor-pointer hover:border-white transition-colors bg-black"
            >
              <input
                ref={panFrontRef}
                type="file"
                accept="image/*,.pdf"
                onChange={(e) => handleFileChange(e, setPanFront)}
                className="hidden"
              />
              {panFront ? (
                <div className="space-y-2">
                  <CheckCircle className="w-8 h-8 mx-auto text-white" strokeWidth={1.5} />
                  <p className="text-xs text-white truncate">{panFront.name}</p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setPanFront(null);
                    }}
                    className="text-xs text-[#888888] hover:text-white transition-colors"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <Upload className="w-8 h-8 mx-auto text-[#888888]" strokeWidth={1.5} />
                  <p className="text-xs text-[#EDEDED]">Upload Front</p>
                  <p className="text-xs text-[#888888]">PNG, JPG, PDF</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Occupation Section */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="border border-[#222222] rounded p-6 mb-6 bg-[#050505]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Briefcase className="w-5 h-5 text-white" strokeWidth={1.5} />
          <h3 className="text-sm font-medium text-[#EDEDED]">
            Occupation <span className="text-red-500">*</span>
          </h3>
        </div>

        <div className="mb-4">
          <label className="block text-xs mb-2 text-[#888888]">Current Occupation</label>
          <select
            value={occupation}
            onChange={(e) => setOccupation(e.target.value)}
            className="w-full bg-black border border-[#222222] rounded px-4 py-3 text-sm focus:outline-none focus:border-white transition-colors text-[#EDEDED]"
          >
            <option value="">Select Occupation</option>
            <option value="software-engineer">Software Engineer</option>
            <option value="doctor">Doctor</option>
            <option value="lawyer">Lawyer</option>
            <option value="accountant">Accountant</option>
            <option value="teacher">Teacher</option>
            <option value="artist">Artist</option>
            <option value="business-owner">Business Owner</option>
            <option value="freelancer">Freelancer</option>
            <option value="student">Student</option>
            <option value="retired">Retired</option>
            <option value="homemaker">Homemaker</option>
            <option value="salaried-employee">Salaried Employee</option>
            <option value="other">Other</option>
          </select>
        </div>

        {occupation === 'other' && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-0"
          >
            <label className="block text-xs mb-2 text-[#888888]">Please specify your occupation</label>
            <input
              type="text"
              value={otherOccupation}
              onChange={(e) => setOtherOccupation(e.target.value)}
              placeholder="Enter your occupation"
              className="w-full bg-black border border-[#222222] rounded px-4 py-3 text-sm focus:outline-none focus:border-white transition-colors text-[#EDEDED]"
            />
          </motion.div>
        )}
      </motion.div>

      {/* Secondary ID Section */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="border border-[#222222] rounded p-6 mb-6 bg-[#050505]"
      >
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-white" strokeWidth={1.5} />
          <h3 className="text-sm font-medium text-[#EDEDED]">
            Secondary ID <span className="text-red-500">*</span>
          </h3>
        </div>

        {/* ID Type Selection */}
        <div className="mb-4">
          <label className="block text-xs mb-2 text-[#888888]">Select ID Type</label>
          <select
            value={secondaryIdType}
            onChange={(e) => {
              setSecondaryIdType(e.target.value as SecondaryIdType);
              setSecondaryIdNumber('');
              setSecondaryIdError('');
              setSecondaryVerifyStatus('idle');
              setSecondaryVerifyResult(null);
            }}
            className="w-full bg-black border border-[#222222] rounded px-4 py-3 text-sm focus:outline-none focus:border-white transition-colors text-[#EDEDED]"
          >
            <option value="">Choose ID Type</option>
            <option value="aadhaar">Aadhaar Card</option>
            <option value="passport">Passport</option>
            <option value="driving-license">Driving License</option>
          </select>
        </div>

        {/* ID Number Input */}
        {secondaryIdType && (
          <div className="mb-4">
            <label className="block text-xs mb-2 text-[#888888]">
              {secondaryIdType === 'aadhaar' && 'Aadhaar Number'}
              {secondaryIdType === 'passport' && 'Passport Number'}
              {secondaryIdType === 'driving-license' && 'Driving License Number'}
            </label>
            <input
              type="text"
              value={secondaryIdNumber}
              onChange={(e) => handleSecondaryIdNumberChange(e.target.value)}
              placeholder={getSecondaryIdPlaceholder(secondaryIdType)}
              className={`w-full bg-black border ${secondaryIdError ? 'border-red-500' : secondaryVerifyStatus === 'success' ? 'border-emerald-700' : 'border-[#222222]'} rounded px-4 py-3 text-sm focus:outline-none focus:border-white transition-colors text-[#EDEDED] uppercase`}
            />
            {secondaryIdError && (
              <div className="flex items-center gap-1 mt-1">
                <AlertCircle className="w-3 h-3 text-red-500" />
                <p className="text-xs text-red-500">{secondaryIdError}</p>
              </div>
            )}
            <p className="text-xs text-[#666666] mt-1">
              {getSecondaryIdHelpText(secondaryIdType)}
            </p>

            {/* Secondary ID Verification Badge */}
            <VerifyBadge status={secondaryVerifyStatus} result={secondaryVerifyResult} />
          </div>
        )}

        {/* Document Upload */}
        {secondaryIdType && (
          <div>
            <label className="block text-xs mb-2 text-[#888888]">Upload Document</label>
            <div
              onClick={() => secondaryIdRef.current?.click()}
              className="border-2 border-dashed border-[#222222] rounded p-8 text-center cursor-pointer hover:border-white transition-colors bg-black"
            >
              <input
                ref={secondaryIdRef}
                type="file"
                accept="image/*,.pdf"
                onChange={(e) => handleFileChange(e, setSecondaryIdDoc)}
                className="hidden"
              />
              {secondaryIdDoc ? (
                <div className="space-y-3">
                  <CheckCircle className="w-12 h-12 mx-auto text-white" strokeWidth={1.5} />
                  <p className="text-sm text-white">{secondaryIdDoc.name}</p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSecondaryIdDoc(null);
                    }}
                    className="text-xs text-[#888888] hover:text-white transition-colors"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="w-12 h-12 mx-auto text-[#888888]" strokeWidth={1.5} />
                  <div>
                    <p className="text-sm text-[#EDEDED] mb-1">Click to upload</p>
                    <p className="text-xs text-[#888888]">PNG, JPG, PDF up to 10MB</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </motion.div>

      {/* Tips */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="border border-[#222222] rounded p-6 mb-8 bg-[#050505]"
      >
        <h3 className="text-sm font-medium mb-4 text-[#EDEDED]">Tips for best results</h3>
        <ul className="space-y-2 text-xs text-[#888888]">
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" strokeWidth={1.5} />
            <span>Ensure all text is clearly visible and in focus</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" strokeWidth={1.5} />
            <span>Place document on a dark, plain background</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" strokeWidth={1.5} />
            <span>Avoid glare and shadows on the document</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" strokeWidth={1.5} />
            <span>Double-check ID numbers for accuracy</span>
          </li>
        </ul>
      </motion.div>

      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        whileHover={{ scale: isFormValid ? 1.01 : 1 }}
        whileTap={{ scale: isFormValid ? 0.99 : 1 }}
        onClick={handleSubmit}
        disabled={!isFormValid}
        className="w-full bg-white text-black py-3 rounded text-sm hover:bg-[#EDEDED] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        Continue to Liveness Check
      </motion.button>
    </div>
  );
}