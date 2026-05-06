// scripts/add.ts
import { ethers } from "hardhat";

// const contractAddress = "0x000008e4e9597890e93f60b4d8dd3610e1700000";
const contractAddress = "0xfc3c9556c77CEE1021231505f53D0FFB0708235c";
const ABI = [
  { "inputs": [], "stateMutability": "nonpayable", "type": "constructor" },
  {
    "inputs":[{"internalType":"address","name":"_user","type":"address"}],
    "name":"add","outputs":[], "stateMutability":"nonpayable", "type":"function"
  },
  {
    "inputs":[], "name":"badAddress",
    "outputs":[{"internalType":"address payable","name":"","type":"address"}],
    "stateMutability":"view","type":"function"
  },
  { "inputs":[], "name":"bk", "outputs":[{"internalType":"address[]","name":"","type":"address[]"}], "stateMutability":"view","type":"function" },
  { "inputs":[], "name":"claim", "outputs":[], "stateMutability":"payable", "type":"function" },
  {
    "inputs":[{"internalType":"address","name":"_user","type":"address"}],
    "name":"inBL", "outputs":[{"internalType":"bool","name":"","type":"bool"}],
    "stateMutability":"nonpayable","type":"function"
  },
  { "inputs":[], "name":"owner", "outputs":[{"internalType":"address","name":"","type":"address"}], "stateMutability":"view","type":"function" },
  { "inputs":[], "name":"pay", "outputs":[], "stateMutability":"payable","type":"function" },
  {
    "inputs":[{"internalType":"address payable","name":"_myAddress","type":"address"}],
    "name":"setBA", "outputs":[], "stateMutability":"nonpayable","type":"function"
  },
  { "stateMutability":"payable","type":"receive" }
] as const;

// Minimal parser for --user=0x... (avoids pulling in a third-party CLI lib)
function getCliArg(name: string): string | undefined {
  const prefix = `--${name}=`;
  const arg = process.argv.find(a => a.startsWith(prefix));
  return arg?.slice(prefix.length);
}

async function main() {
  const [signer] = await ethers.getSigners();
  const contract = new ethers.Contract(contractAddress, ABI, signer);

  const argUser = getCliArg("user");
  const user = argUser ?? await signer.getAddress();

  // Optional: if inBL means "is on the blacklist", you could query it here.
  // Caveat: inBL is nonpayable (sends a tx); don't call it here if it mutates state.
  // const inBL = await contract.inBL.staticCall(user).catch(() => null);
  // console.log("inBL(static) =>", inBL);

  console.log(`Using signer: ${await signer.getAddress()}`);
  console.log(`Calling add(${user}) ...`);

  const estGas = await contract.add.estimateGas(user).catch(() => null);
  if (estGas) console.log(`Estimated gas: ${estGas.toString()}`);

  const tx = await contract.add(user);
  console.log("add tx hash:", tx.hash);

  const confirmations = Number(process.env.CONFIRMATIONS ?? "1");
  const receipt = await tx.wait(confirmations);
  console.log(`add confirmed in block: ${receipt.blockNumber} (conf=${confirmations})`);
  console.log("✅ add done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

